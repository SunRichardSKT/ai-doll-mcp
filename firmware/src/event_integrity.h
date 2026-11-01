#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

static uint32_t eventCRC32(const char* bytes,size_t length,uint32_t seed=0){
 uint32_t crc=~seed;
 for(size_t i=0;i<length;i++){
  crc^=(uint8_t)bytes[i];
  for(int bit=0;bit<8;bit++)crc=(crc>>1)^((crc&1)?0xedb88320UL:0);
 }
 return ~crc;
}

// Exact canonical LittleFS filename; avoids linking the general scanf engine.
static bool eventFileId(const char* path,uint64_t &id){
 if(strlen(path)!=33||memcmp(path,"/doll-event-",12)||strcmp(path+28,".json"))return false;
 uint64_t value=0;
 for(int i=12;i<28;i++){
  char c=path[i];int nibble=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
  if(nibble<0)return false;
  value=(value<<4)|(uint64_t)nibble;
 }
 id=value;return true;
}
