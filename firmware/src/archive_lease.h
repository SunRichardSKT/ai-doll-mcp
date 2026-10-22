#pragma once
#include <stdint.h>
#include <string.h>

// Volatile, single-owner archive coordination. No NVS writes or wall clock.
// Kept independent of Arduino so expiry and ownership run in native tests too.
struct ArchiveLeaseState {
 static constexpr uint64_t TTL_MS=90000;
 char owner[97]={},kind[9]={},id[33]={};
 uint64_t expires=0,delivered=0;

 void clear(){owner[0]=kind[0]=id[0]=0;expires=delivered=0;}
 bool active(uint64_t now){if(expires&&now>=expires)clear();return expires!=0;}
 static bool ownerValid(const char* value){
  size_t n=value?strlen(value):0;if(!n||n>96)return false;
  for(size_t i=0;i<n;i++){char c=value[i];if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c==':'||c=='.'))return false;}
  return true;
 }
 static bool kindValid(const char* value){return value&&(!strcmp(value,"phone")||!strcmp(value,"computer")||!strcmp(value,"server"));}
 static bool idValid(const char* value){
  if(!value||strlen(value)!=32)return false;
  for(int i=0;i<32;i++)if(!((value[i]>='0'&&value[i]<='9')||(value[i]>='a'&&value[i]<='f')))return false;
  return true;
 }
 bool matches(const char* value,uint64_t now){return active(now)&&value&&!strcmp(id,value);}
 // 0=acquired/recovered, 1=busy, 2=invalid. A repeated acquire after a lost
 // response returns the same lease and retains its delivered cursor.
 int acquire(const char* collector,const char* type,const char* candidate,uint64_t now){
  if(!ownerValid(collector)||!kindValid(type)||!idValid(candidate))return 2;
  if(active(now)){
   if(strcmp(owner,collector)||strcmp(kind,type))return 1;
  }else{strcpy(owner,collector);strcpy(kind,type);strcpy(id,candidate);delivered=0;}
  expires=now+TTL_MS;return 0;
 }
 bool renew(const char* value,uint64_t now){if(!matches(value,now))return false;expires=now+TTL_MS;return true;}
 bool release(const char* value,uint64_t now){
  if(!idValid(value))return false;
  if(!active(now))return true;
  if(!matches(value,now))return false;
  clear();return true;
 }
 bool record(const char* value,uint64_t cursor,uint64_t now){
  if(!matches(value,now))return false;
  if(cursor>delivered)delivered=cursor;
  return true;
 }
 bool canAck(const char* value,uint64_t cursor,uint64_t now){return matches(value,now)&&cursor>0&&cursor<=delivered;}
};
