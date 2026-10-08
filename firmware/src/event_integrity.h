#pragma once
#include <stdint.h>
#include <stddef.h>

static uint32_t eventCRC32(const char* bytes,size_t length,uint32_t seed=0){
 uint32_t crc=~seed;
 for(size_t i=0;i<length;i++){
  crc^=(uint8_t)bytes[i];
  for(int bit=0;bit<8;bit++)crc=(crc>>1)^((crc&1)?0xedb88320UL:0);
 }
 return ~crc;
}
