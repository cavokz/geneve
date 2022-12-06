# Preface

This document collects various considerations I've been making while working at Geneve. It's to
be considered a work in progress, not necessarily meaningful, complete and/or correct in any way.

It is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

# Introduction

A basic form of data generation is reading bytes from a source of randomness, eg:

```
$ hexdump -C -n 32 /dev/random
00000000  73 fc 80 81 94 93 c2 c8  14 d1 09 ee b2 01 04 08  |s...............|
00000010  77 6f 14 44 b3 93 69 0e  15 7b 84 de cc 1c d5 c0  |wo.D..i..{......|
00000020
```

Depending on the entropy of the source, this could be all is needed for some cryptographical uses.

For our needs instead, data is represented by documents containing _field-value_ pairs where field names
induce a hierarchical structure and field types loosely describe the set of values they can contain.

Here the example above in a possible document form:

```
random:
  num_bits: 256
  value: 0x73fc80819493c2c814d109eeb2010408776f1444b393690e157b84decc1cd5c0
```

A more elaborated example:

```
lighthouses:
 - name: Wolf Rock
   country: United Kingdom
   location:
     lat: 49.95
     lon: 5.82
   tower:
     height: 41m
     material: granite
   light:
     focal_height: 34m
     range: 16nmi
```

Here at the X-rays, with explicit field names and types:

```
lighthouses.name: text
lighthouses.location.lat: float
lighthouses.location.lon: float
lighthouses.tower.height: text
lighthouses.tower.material: text
lighthouses.light.focal_height: text
lighthouses.light.range: text
```

We can already make some useful observations.

_Types do not say everything._ For instance, both `lighthouses.location.lat` and `lighthouses.location.lon` are marked as float numbers but are also subject to other limits. Indeed `lat` ∈ [-90, +90] and `lon` ∈ [-180, +180], generating them requires satisfying these additional constraints.

_Some fields might depend on each other._ In the crypto example, `random.num_bits` is expected to match the length of `random.value`. In the lighthouses one, `location` is expected to be in UK, as per `country`. This implies that only some fields can be generated independently from each other, possibily at different times, whereas others need to be generated together and avoiding invalid combinations.

In a first attempt we could say that generating data is about drawing documents from a solution space having as many dimensions as the number of possible fields (each dimension accounting for all the possible values of the given field) where all the invalid combinations have been removed.
