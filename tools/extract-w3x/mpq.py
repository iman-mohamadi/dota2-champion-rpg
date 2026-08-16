#!/usr/bin/env python3
"""Dependency-free MPQ (Warcraft III .w3x/.w3m) archive reader.

Implements the MPQ v0/v1 format: crypt table, hash/block tables, sector
decompression (zlib, bzip2, sparse, PKWare DCL implode) and file decryption.

Written because `smpq`/StormLib need root to install and there is no pip in this
environment. Pure stdlib.
"""
import bz2
import os
import struct
import zlib

# ---------------------------------------------------------------- crypt table

def _make_crypt_table():
    table = [0] * 0x500
    seed = 0x00100001
    for i in range(0x100):
        idx = i
        for _ in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            t1 = (seed & 0xFFFF) << 16
            seed = (seed * 125 + 3) % 0x2AAAAB
            t2 = seed & 0xFFFF
            table[idx] = (t1 | t2) & 0xFFFFFFFF
            idx += 0x100
    return table


CRYPT = _make_crypt_table()

HASH_TABLE_OFFSET, HASH_NAME_A, HASH_NAME_B, HASH_FILE_KEY = 0, 1, 2, 3


def mpq_hash(string, hash_type):
    seed1, seed2 = 0x7FED7FED, 0xEEEEEEEE
    for ch in string.upper().replace("/", "\\"):
        c = ord(ch)
        seed1 = (CRYPT[(hash_type << 8) + c] ^ (seed1 + seed2)) & 0xFFFFFFFF
        seed2 = (c + seed1 + seed2 + (seed2 << 5) + 3) & 0xFFFFFFFF
    return seed1


def decrypt(data, key):
    """Decrypt a bytes-like whose length is a multiple of 4."""
    out = bytearray(data)
    n = len(out) // 4
    seed1, seed2 = key & 0xFFFFFFFF, 0xEEEEEEEE
    vals = list(struct.unpack("<%dI" % n, bytes(out[: n * 4])))
    for i in range(n):
        seed2 = (seed2 + CRYPT[0x400 + (seed1 & 0xFF)]) & 0xFFFFFFFF
        ch = vals[i] ^ ((seed1 + seed2) & 0xFFFFFFFF)
        seed1 = ((((~seed1) << 0x15) & 0xFFFFFFFF) + 0x11111111 | (seed1 >> 0x0B)) & 0xFFFFFFFF
        seed2 = (ch + seed2 + (seed2 << 5) + 3) & 0xFFFFFFFF
        vals[i] = ch
    out[: n * 4] = struct.pack("<%dI" % n, *vals)
    return bytes(out)


# ------------------------------------------------------- PKWare DCL "explode"

_DIST_BITS = [
    2, 4, 4, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
]
_DIST_CODE = [
    0x03, 0x0D, 0x05, 0x19, 0x09, 0x11, 0x01, 0x3E, 0x1E, 0x2E, 0x0E, 0x36,
    0x16, 0x26, 0x06, 0x3A, 0x1A, 0x2A, 0x0A, 0x32, 0x12, 0x22, 0x02, 0x7C,
    0x3C, 0x5C, 0x1C, 0x6C, 0x2C, 0x4C, 0x0C, 0x74, 0x34, 0x54, 0x14, 0x64,
    0x24, 0x44, 0x04, 0x78, 0x38, 0x58, 0x18, 0x68, 0x28, 0x48, 0x08, 0xF0,
    0x70, 0xB0, 0x30, 0xD0, 0x50, 0x90, 0x10, 0xE0, 0x60, 0xA0, 0x20, 0xC0,
    0x40, 0x80, 0x00,
]
_LEN_BITS = [3, 2, 3, 3, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 7, 7]
_LEN_CODE = [0x05, 0x03, 0x01, 0x06, 0x0A, 0x02, 0x0C, 0x14,
             0x04, 0x18, 0x08, 0x30, 0x10, 0x20, 0x40, 0x00]
_LEN_BASE = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
             0x08, 0x0A, 0x0E, 0x16, 0x26, 0x46, 0x86, 0x106]
_EXTRA_LEN_BITS = [0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8]


def _build_decode(codes, bits):
    """Map (code, nbits) -> symbol for LSB-first bit reading."""
    table = {}
    for sym, (code, nb) in enumerate(zip(codes, bits)):
        table[(nb, code)] = sym
    return table


_DIST_DEC = _build_decode(_DIST_CODE, _DIST_BITS)
_LEN_DEC = _build_decode(_LEN_CODE, _LEN_BITS)


class _BitReader:
    def __init__(self, data):
        self.data, self.pos, self.bit = data, 0, 0

    def read(self, n):
        v = 0
        for i in range(n):
            if self.pos >= len(self.data):
                raise EOFError
            b = (self.data[self.pos] >> self.bit) & 1
            v |= b << i
            self.bit += 1
            if self.bit == 8:
                self.bit = 0
                self.pos += 1
        return v

    def decode(self, table, maxbits=8):
        code, nb = 0, 0
        for _ in range(maxbits):
            code = (code << 1) | self.read(1)
            nb += 1
            if (nb, code) in table:
                return table[(nb, code)]
        raise ValueError("bad prefix code")


def pk_explode(data):
    """PKWare Data Compression Library 'implode' decompressor."""
    if len(data) < 4:
        raise ValueError("pkware: too short")
    lit_mode, dict_bits = data[0], data[1]
    if lit_mode not in (0, 1) or not 4 <= dict_bits <= 6:
        raise ValueError("pkware: bad header %d/%d" % (lit_mode, dict_bits))
    if lit_mode == 1:
        raise NotImplementedError("pkware: coded literals unsupported")
    br = _BitReader(data[2:])
    out = bytearray()
    dict_mask = (1 << dict_bits) - 1
    while True:
        try:
            if br.read(1):  # length/distance pair
                li = br.decode(_LEN_DEC, 8)
                length = _LEN_BASE[li]
                extra = _EXTRA_LEN_BITS[li]
                if extra:
                    length += br.read(extra)
                length += 2
                if length == 519:  # end of stream
                    break
                di = br.decode(_DIST_DEC, 8)
                if length == 2:
                    dist = (di << 2) | br.read(2)
                else:
                    dist = (di << dict_bits) | br.read(dict_bits)
                dist += 1
                for _ in range(length):
                    out.append(out[-dist])
            else:
                out.append(br.read(8))
        except EOFError:
            break
    return bytes(out)


def _sparse_decompress(data):
    out = bytearray()
    i = 0
    while i < len(data):
        ctl = data[i]
        i += 1
        if ctl & 0x80:
            n = (ctl & 0x7F) + 1
            out += data[i:i + n]
            i += n
        else:
            out += b"\x00" * (ctl + 3)
    return bytes(out)


def decompress(data):
    """Multi-compression sector: first byte is a mask of methods applied."""
    if not data:
        return data
    mask, body = data[0], data[1:]
    if mask == 0x02:
        return zlib.decompress(body)
    if mask == 0x08:
        return pk_explode(body)
    if mask == 0x10:
        return bz2.decompress(body)
    if mask == 0x20:
        return _sparse_decompress(body)
    if mask == 0x12:
        raise NotImplementedError("LZMA sector")
    if mask & 0x40 or mask & 0x01:
        raise NotImplementedError("audio/huffman sector (mask 0x%02x)" % mask)
    raise NotImplementedError("compression mask 0x%02x" % mask)


# ------------------------------------------------------------------- archive

FLAG_EXISTS = 0x80000000
FLAG_SINGLE_UNIT = 0x01000000
FLAG_FIX_KEY = 0x00020000
FLAG_ENCRYPTED = 0x00010000
FLAG_COMPRESSED = 0x00000200
FLAG_IMPLODED = 0x00000100


class MPQArchive:
    def __init__(self, path):
        self.f = open(path, "rb")
        raw = self.f.read(0x2000)
        self.offset = raw.find(b"MPQ\x1a")
        if self.offset < 0:
            raise ValueError("no MPQ header found")
        self.f.seek(self.offset)
        hdr = self.f.read(32)
        (magic, self.header_size, self.archive_size, self.format_version,
         self.block_size_shift, hash_off, block_off,
         self.hash_count, self.block_count) = struct.unpack("<4sIIHHIIII", hdr)
        self.sector_size = 512 << self.block_size_shift

        self.f.seek(self.offset + hash_off)
        ht = decrypt(self.f.read(self.hash_count * 16), mpq_hash("(hash table)", HASH_FILE_KEY))
        self.hash_table = [struct.unpack("<IIHHI", ht[i * 16:(i + 1) * 16])
                           for i in range(self.hash_count)]

        self.f.seek(self.offset + block_off)
        bt = decrypt(self.f.read(self.block_count * 16), mpq_hash("(block table)", HASH_FILE_KEY))
        self.block_table = [struct.unpack("<IIII", bt[i * 16:(i + 1) * 16])
                            for i in range(self.block_count)]

    def find(self, name):
        idx = mpq_hash(name, HASH_TABLE_OFFSET) & (self.hash_count - 1)
        a, b = mpq_hash(name, HASH_NAME_A), mpq_hash(name, HASH_NAME_B)
        for i in range(self.hash_count):
            e = self.hash_table[(idx + i) & (self.hash_count - 1)]
            if e[4] == 0xFFFFFFFF:
                return None
            if e[0] == a and e[1] == b and e[4] != 0xFFFFFFFE:
                return e[4]
        return None

    def read(self, name):
        bi = self.find(name)
        if bi is None or bi >= len(self.block_table):
            return None
        offset, csize, size, flags = self.block_table[bi]
        if not flags & FLAG_EXISTS or size == 0:
            return None
        self.f.seek(self.offset + offset)
        raw = self.f.read(csize)

        key = None
        if flags & FLAG_ENCRYPTED:
            base = name.replace("/", "\\").split("\\")[-1]
            key = mpq_hash(base, HASH_FILE_KEY)
            if flags & FLAG_FIX_KEY:
                key = ((key + offset) ^ size) & 0xFFFFFFFF

        compressed = flags & (FLAG_COMPRESSED | FLAG_IMPLODED)

        if flags & FLAG_SINGLE_UNIT:
            if key is not None:
                raw = decrypt(raw, key)
            if not compressed or csize == size:
                return raw[:size]
            if flags & FLAG_IMPLODED and not flags & FLAG_COMPRESSED:
                return pk_explode(raw)[:size]
            return decompress(raw)[:size]

        nsectors = (size + self.sector_size - 1) // self.sector_size
        if not compressed:
            if key is not None:
                raw = decrypt(raw, key)
            return raw[:size]

        ntable = nsectors + 1
        tbl = raw[: ntable * 4]
        if key is not None:
            tbl = decrypt(tbl, (key - 1) & 0xFFFFFFFF)
        positions = struct.unpack("<%dI" % ntable, tbl)

        out = bytearray()
        for i in range(nsectors):
            start, end = positions[i], positions[i + 1]
            chunk = raw[start:end]
            if key is not None:
                chunk = decrypt(chunk, (key + i) & 0xFFFFFFFF)
            expect = min(self.sector_size, size - len(out))
            if len(chunk) == expect:
                out += chunk
            elif flags & FLAG_IMPLODED and not flags & FLAG_COMPRESSED:
                out += pk_explode(chunk)
            else:
                out += decompress(chunk)
        return bytes(out[:size])

    def close(self):
        self.f.close()
