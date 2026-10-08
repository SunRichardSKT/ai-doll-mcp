#include <cassert>
#include <cstring>
#include <cstdio>
#include "../firmware/src/event_integrity.h"
int main(){
 const char* vector="123456789";
 assert(eventCRC32(vector,9)==0xcbf43926U);
 assert(eventCRC32("",0)==0);
 uint32_t prefix=eventCRC32(vector,4);
 assert(eventCRC32(vector+4,5,prefix)==eventCRC32(vector,9));
 const char* event="1\nepoch\nboot\n{\"body_part\":\"头顶\",\"source\":\"simulation\"}";
 char changed[128];strcpy(changed,event);changed[strlen(changed)-2]^=1;
 assert(eventCRC32(event,strlen(event))!=eventCRC32(changed,strlen(changed)));
 puts("PASS: CRC32 standard vector, incremental header/payload and mutation detection");
}
