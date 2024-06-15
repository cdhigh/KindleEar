""" 
Copyright by https://github.com/zhansliu/writemdict

ripemd128.py - A simple ripemd128 library in pure Python.

Supports both Python 2 (versions >= 2.6) and Python 3.

Usage:
    from ripemd128 import ripemd128
    digest = ripemd128(b"The quick brown fox jumps over the lazy dog")
    assert(digest == b"\x3f\xa9\xb5\x7f\x05\x3c\x05\x3f\xbe\x27\x35\xb2\x38\x0d\xb5\x96")

"""
      


import struct


# follows this description: http://homes.esat.kuleuven.be/~bosselae/ripemd/rmd128.txt

def f(j, x, y, z):
	assert(0 <= j and j < 64)
	if j < 16:
		return x ^ y ^ z
	elif j < 32:
		return (x & y) | (z & ~x)
	elif j < 48:
		return (x | (0xffffffff & ~y)) ^ z
	else:
		return (x & z) | (y & ~z)

def K(j):
	assert(0 <= j and j < 64)
	if j < 16:
		return 0x00000000
	elif j < 32:
		return 0x5a827999
	elif j < 48:
		return 0x6ed9eba1
	else:
		return 0x8f1bbcdc

def Kp(j):
	assert(0 <= j and j < 64)
	if j < 16:
		return 0x50a28be6
	elif j < 32:
		return 0x5c4dd124
	elif j < 48:
		return 0x6d703ef3
	else:
		return 0x00000000

def padandsplit(message):
	"""
	returns a two-dimensional array X[i][j] of 32-bit integers, where j ranges
	from 0 to 16.
	First pads the message to length in bytes is congruent to 56 (mod 64), 
	by first adding a byte 0x80, and then padding with 0x00 bytes until the
	message length is congruent to 56 (mod 64). Then adds the little-endian
	64-bit representation of the original length. Finally, splits the result
	up into 64-byte blocks, which are further parsed as 32-bit integers.
	"""
	origlen = len(message)
	padlength = 64 - ((origlen - 56) % 64) #minimum padding is 1!
	message += b"\x80"
	message += b"\x00" * (padlength - 1)
	message += struct.pack("<Q", origlen*8)
	assert(len(message) % 64 == 0)
	return [
	         [
	           struct.unpack("<L", message[i+j:i+j+4])[0]
	           for j in range(0, 64, 4)
	         ]
	         for i in range(0, len(message), 64)
	       ]


def add(*args):
	return sum(args) & 0xffffffff

def rol(s,x):
	assert(s < 32)
	return (x << s | x >> (32-s)) & 0xffffffff

r =  [ 0, 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,13,14,15,
       7, 4,13, 1,10, 6,15, 3,12, 0, 9, 5, 2,14,11, 8,
       3,10,14, 4, 9,15, 8, 1, 2, 7, 0, 6,13,11, 5,12,
       1, 9,11,10, 0, 8,12, 4,13, 3, 7,15,14, 5, 6, 2]
rp = [ 5,14, 7, 0, 9, 2,11, 4,13, 6,15, 8, 1,10, 3,12,
       6,11, 3, 7, 0,13, 5,10,14,15, 8,12, 4, 9, 1, 2,
      15, 5, 1, 3, 7,14, 6, 9,11, 8,12, 2,10, 0, 4,13,
       8, 6, 4, 1, 3,11,15, 0, 5,12, 2,13, 9, 7,10,14]
s =  [11,14,15,12, 5, 8, 7, 9,11,13,14,15, 6, 7, 9, 8,
       7, 6, 8,13,11, 9, 7,15, 7,12,15, 9,11, 7,13,12,
      11,13, 6, 7,14, 9,13,15,14, 8,13, 6, 5,12, 7, 5,
      11,12,14,15,14,15, 9, 8, 9,14, 5, 6, 8, 6, 5,12]
sp = [ 8, 9, 9,11,13,15,15, 5, 7, 7, 8,11,14,14,12, 6,
       9,13,15, 7,12, 8, 9,11, 7, 7,12, 7, 6,15,13,11,
       9, 7,15,11, 8, 6, 6,14,12,13, 5,14,13,13, 7, 5,
      15, 5, 8,11,14,14, 6,14, 6, 9,12, 9,12, 5,15, 8]


def ripemd128(message):
	h0 = 0x67452301
	h1 = 0xefcdab89
	h2 = 0x98badcfe
	h3 = 0x10325476
	X = padandsplit(message)
	for i in range(len(X)):
		(A,B,C,D) = (h0,h1,h2,h3)
		(Ap,Bp,Cp,Dp) = (h0,h1,h2,h3)
		for j in range(64):
			T = rol(s[j], add(A, f(j,B,C,D), X[i][r[j]], K(j)))
			(A,D,C,B) = (D,C,B,T)
			T = rol(sp[j], add(Ap, f(63-j,Bp,Cp,Dp), X[i][rp[j]], Kp(j)))
			(Ap,Dp,Cp,Bp)=(Dp,Cp,Bp,T)
		T = add(h1,C,Dp)
		h1 = add(h2,D,Ap)
		h2 = add(h3,A,Bp)
		h3 = add(h0,B,Cp)
		h0 = T
	
	
	return struct.pack("<LLLL",h0,h1,h2,h3)

def hexstr(bstr):
	return "".join("{0:02x}".format(b) for b in bstr)
	
