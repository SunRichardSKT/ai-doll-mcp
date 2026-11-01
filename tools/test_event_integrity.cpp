#include <cassert>
#include <cstring>
#include <cstdio>
#include <initializer_list>
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
 uint64_t parsed=0;
 assert(eventFileId("/doll-event-0000000000000001.json",parsed)&&parsed==1);
 for(const char* bad:{"/doll-event-1.json","/doll-event-000000000000000A.json","/doll-event-0000000000000001.json.tmp","/doll-event-+000000000000001.json","/other-0000000000000001.json"})assert(!eventFileId(bad,parsed));
 uint64_t v=1;
 for(int i=0;i<10000;i++){
  char name[64];snprintf(name,sizeof(name),"/doll-event-%016llx.json",(unsigned long long)v);
  unsigned long long old=0;char canonical[64];bool legacy=sscanf(name,"/doll-event-%16llx.json",&old)==1;
  snprintf(canonical,sizeof(canonical),"/doll-event-%016llx.json",old);legacy=legacy&&!strcmp(name,canonical)&&old>0&&old<=9007199254740991ULL;
  bool current=eventFileId(name,parsed)&&parsed>0&&parsed<=9007199254740991ULL;assert(legacy==current);assert(parsed==v);
  v=v*6364136223846793005ULL+1;
 }
 puts("PASS: CRC32, canonical archive filenames and 10000 legacy round trips");
}
