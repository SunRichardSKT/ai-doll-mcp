#pragma once
#include <LittleFS.h>
#include <esp_partition.h>
#include <sys/time.h>
#include "event_integrity.h"

static constexpr size_t EVENT_DISK_CAP=256,EVENT_FILE_MAX=1536;
static constexpr uint64_t EVENT_ID_MAX=9007199254740991ULL;
static uint64_t eventDiskIds[EVENT_DISK_CAP]={};
static size_t eventDiskCount=0;
static uint64_t eventNextId=0,eventReservedEnd=0,eventDelivered=0,eventAcked=0;
static uint64_t eventLost=0,eventCorrupt=0,eventWriteFailures=0;
static bool eventStorageReady=false,eventClockSynced=false;
static String eventStorageEpoch,eventStorageError="not_initialized";

static uint64_t deviceWallTime(){
 if(!eventClockSynced)return 0;
 timeval now;gettimeofday(&now,nullptr);
 return now.tv_sec>=1704067200LL?(uint64_t)now.tv_sec*1000+now.tv_usec/1000:0;
}
static String eventFileName(uint64_t id){
 char path[48];snprintf(path,sizeof(path),"/doll-event-%016llx.json",(unsigned long long)id);return String(path);
}
static uint32_t storedCRC(uint64_t id,const String &epoch,const String &boot,const String &payload){
 String header=String((unsigned long long)id)+"\n"+epoch+"\n"+boot+"\n";
 uint32_t crc=eventCRC32(header.c_str(),header.length());return eventCRC32(payload.c_str(),payload.length(),crc);
}
static bool hexIdentity(const String &value){
 if(value.length()!=32)return false;
 for(size_t i=0;i<32;i++)if(!((value[i]>='0'&&value[i]<='9')||(value[i]>='a'&&value[i]<='f')))return false;
 return true;
}
static bool loadStoredEvent(uint64_t id,JsonDocument &record,JsonDocument &payload){
 File file=LittleFS.open(eventFileName(id),FILE_READ);
 if(!file||file.size()>EVENT_FILE_MAX){if(file)file.close();return false;}
 auto error=deserializeJson(record,file);file.close();if(error)return false;
 if(!record["schema"].is<int>()||record["schema"].as<int>()!=1||!record["storage_id"].is<uint64_t>()||record["storage_id"].as<uint64_t>()!=id||
    !record["event_json"].is<String>()||!record["crc32"].is<uint32_t>())return false;
 String epoch=record["storage_epoch"]|"",boot=record["boot_id"]|"",wire=record["event_json"]|"";
 if(!hexIdentity(epoch)||!hexIdentity(boot)||record["crc32"].as<uint32_t>()!=storedCRC(id,epoch,boot,wire))return false;
 if(deserializeJson(payload,wire)||!payload["seq"].is<uint32_t>()||payload["seq"].as<uint32_t>()==0)return false;
 return payload["event_id"].as<String>()==boot+"-"+String(payload["seq"].as<uint32_t>());
}
static bool eventPartitionBlank(){
 const esp_partition_t* partition=esp_partition_find_first(ESP_PARTITION_TYPE_DATA,ESP_PARTITION_SUBTYPE_DATA_SPIFFS,"spiffs");
 if(!partition)return false;
 uint8_t buffer[256];
 for(size_t offset=0;offset<partition->size;offset+=sizeof(buffer)){
  size_t count=min(sizeof(buffer),(size_t)(partition->size-offset));
  if(esp_partition_read(partition,offset,buffer,count)!=ESP_OK)return false;
  for(size_t i=0;i<count;i++)if(buffer[i]!=0xff)return false;
 }
 return true;
}
static bool reserveEventIds(){
 if(eventNextId>=EVENT_ID_MAX-256){eventStorageError="event_id_exhausted";return false;}
 uint64_t end=eventNextId+256;
 if(prefs.putULong64("ev_hi",end)!=sizeof(uint64_t)){eventStorageError="counter_save_failed";return false;}
 eventReservedEnd=end;return true;
}
static void eraseIndex(size_t index){
 for(size_t i=index+1;i<eventDiskCount;i++)eventDiskIds[i-1]=eventDiskIds[i];
 eventDiskCount--;
}
static bool evictOldest(){
 if(!eventDiskCount||!LittleFS.remove(eventFileName(eventDiskIds[0]))){eventStorageError="queue_reclaim_failed";return false;}
 eraseIndex(0);eventLost++;prefs.putULong64("ev_lost",eventLost);return true;
}
static void __attribute__((noinline)) eventStorageInit(){
 eventLost=prefs.getULong64("ev_lost",0);eventCorrupt=prefs.getULong64("ev_bad",0);
 if(!LittleFS.begin(false)){
  // Never format an occupied or damaged filesystem automatically.
  if(!eventPartitionBlank()||!LittleFS.format()||!LittleFS.begin(false)){eventStorageError="filesystem_unavailable_not_formatted";return;}
 }
 eventStorageEpoch=prefs.getString("ev_epoch","");
 File directory=LittleFS.open("/");File file=directory.openNextFile();uint64_t highest=0;
 while(file){
  String path=file.path();unsigned long long parsed=0;char canonical[48];
  if(sscanf(path.c_str(),"/doll-event-%16llx.json",&parsed)==1){
   uint64_t id=parsed;
   snprintf(canonical,sizeof(canonical),"/doll-event-%016llx.json",(unsigned long long)id);
   if(path==canonical&&id>0&&id<=EVENT_ID_MAX){
    file.close();JsonDocument record,payload;
    if(loadStoredEvent(id,record,payload)&&(eventStorageEpoch.isEmpty()||record["storage_epoch"].as<String>()==eventStorageEpoch)){
     if(eventStorageEpoch.isEmpty())eventStorageEpoch=record["storage_epoch"].as<String>();
     highest=max(highest,id);
     if(eventDiskCount==EVENT_DISK_CAP){
      if(id<eventDiskIds[0]){LittleFS.remove(path);eventLost++;}
      else if(evictOldest()){eventDiskIds[eventDiskCount++]=id;}
     }else eventDiskIds[eventDiskCount++]=id;
     // Filesystem directory order is not event order.
     for(size_t i=eventDiskCount?eventDiskCount-1:0;i>0&&eventDiskIds[i]<eventDiskIds[i-1];i--){uint64_t tmp=eventDiskIds[i];eventDiskIds[i]=eventDiskIds[i-1];eventDiskIds[i-1]=tmp;}
    }else{LittleFS.remove(path);eventCorrupt++;}
   }
  }
  if(file)file.close();
  file=directory.openNextFile();
 }
 directory.close();
 if(LittleFS.exists("/doll-event.tmp")){LittleFS.remove("/doll-event.tmp");eventCorrupt++;}
 if(!hexIdentity(eventStorageEpoch))eventStorageEpoch=randomHex();
 if(prefs.putString("ev_epoch",eventStorageEpoch)!=eventStorageEpoch.length()){eventStorageError="epoch_save_failed";return;}
 prefs.putULong64("ev_lost",eventLost);prefs.putULong64("ev_bad",eventCorrupt);
 eventNextId=max(prefs.getULong64("ev_hi",0),highest)+1;
 if(!reserveEventIds())return;
 eventStorageReady=true;eventStorageError="";
}
static void __attribute__((noinline)) persistTouchRecord(const TouchRecord &event){
 if(!eventStorageReady){eventWriteFailures++;return;}
 if(eventDiskCount==EVENT_DISK_CAP&&!evictOldest()){eventWriteFailures++;return;}
 if(eventNextId>=eventReservedEnd&&!reserveEventIds()){eventWriteFailures++;return;}
 uint64_t id=eventNextId++;JsonDocument record,data;encodeTouchRecord(data.to<JsonObject>(),event,touchBoot);
 String wire=encode(data);record["schema"]=1;record["storage_id"]=id;record["storage_epoch"]=eventStorageEpoch;
 record["boot_id"]=touchBoot;record["event_json"]=wire;record["crc32"]=storedCRC(id,eventStorageEpoch,touchBoot,wire);
 String stored=encode(record);
 if(stored.length()>EVENT_FILE_MAX){eventStorageError="record_too_large";eventWriteFailures++;return;}
 File file=LittleFS.open("/doll-event.tmp",FILE_WRITE);
 if(!file){eventStorageError="queue_write_failed";eventWriteFailures++;return;}
 size_t written=file.print(stored);file.flush();file.close();
 if(written!=stored.length()||!LittleFS.rename("/doll-event.tmp",eventFileName(id))){
  eventStorageError="queue_commit_failed";eventWriteFailures++;return;
 }
 eventDiskIds[eventDiskCount++]=id;eventStorageError="";
}
static void eventStorageStatus(JsonObject out){
 out["available"]=eventStorageReady;out["error"]=eventStorageError;out["storage_epoch"]=eventStorageEpoch;
 out["pending_records"]=eventDiskCount;out["max_records"]=EVENT_DISK_CAP;out["max_record_bytes"]=EVENT_FILE_MAX;
 out["lost_records"]=eventLost;out["corrupt_records"]=eventCorrupt;out["write_failures_since_boot"]=eventWriteFailures;
 out["filesystem_bytes"]=eventStorageReady?LittleFS.totalBytes():0;out["filesystem_used_bytes"]=eventStorageReady?LittleFS.usedBytes():0;
 out["clock_synced"]=eventClockSynced;out["device_time_ms"]=deviceWallTime();out["outputs_replay"]=false;
}
static void __attribute__((noinline)) readEventBacklog(JsonObject out){
 JsonArray entries=out["persistent_events"].to<JsonArray>();uint64_t cursor=0;
 for(size_t i=0;i<eventDiskCount&&entries.size()<24;){
  uint64_t id=eventDiskIds[i];JsonDocument record,payload;
  if(!loadStoredEvent(id,record,payload)){
   if(!LittleFS.remove(eventFileName(id))){eventStorageError="corrupt_reclaim_failed";break;}
   eraseIndex(i);eventCorrupt++;prefs.putULong64("ev_bad",eventCorrupt);continue;
  }
  JsonObject entry=entries.add<JsonObject>();entry["storage_id"]=id;entry["boot_id"]=record["boot_id"];
  entry["event"].set(payload.as<JsonObject>());cursor=id;i++;
 }
 eventDelivered=max(eventDelivered,cursor);
 out["storage_cursor"]=cursor;out["storage_has_more"]=eventDiskCount>entries.size();
 eventStorageStatus(out["event_storage"].to<JsonObject>());
}
static bool acknowledgeStoredEvents(JsonVariantConst arguments,String &error){
 if(!eventStorageReady){error="Persistent storage unavailable";return false;}
 if(!arguments["storage_cursor"].is<uint64_t>()||arguments["boot_id"].as<String>()!=touchBoot||
    arguments["storage_epoch"].as<String>()!=eventStorageEpoch){error="Current boot, storage epoch and integer cursor required";return false;}
 uint64_t cursor=arguments["storage_cursor"].as<uint64_t>();
 if(!cursor||cursor>eventDelivered){error="Only a previously delivered cursor may be acknowledged";return false;}
 while(eventDiskCount&&eventDiskIds[0]<=cursor){
  if(!LittleFS.remove(eventFileName(eventDiskIds[0]))){error="Unable to clear acknowledged event";return false;}
  eraseIndex(0);
 }
 eventAcked=max(eventAcked,cursor);return true;
}
static bool syncDeviceClock(JsonVariantConst arguments,String &error){
 if(!arguments["unix_time_ms"].is<uint64_t>()||arguments["boot_id"].as<String>()!=touchBoot){error="Current boot and unix_time_ms integer required";return false;}
 uint64_t ms=arguments["unix_time_ms"].as<uint64_t>();
 if(ms<1704067200000ULL||ms>4102444800000ULL){error="Time must be within 2024..2100 UTC";return false;}
 timeval now={(time_t)(ms/1000),(suseconds_t)((ms%1000)*1000)};
 if(settimeofday(&now,nullptr)){error="Clock update failed";return false;}
 eventClockSynced=true;return true;
}
