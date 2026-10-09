#pragma once
#include <stdint.h>
#include <stddef.h>
#include <math.h>

// Portable DS18B20 decoding. Wire byte order is preserved in ROM strings.
static uint8_t ds18Crc(const uint8_t* bytes,size_t count){
 uint8_t crc=0;
 for(size_t i=0;i<count;i++){uint8_t value=bytes[i];for(int bit=0;bit<8;bit++){bool mix=(crc^value)&1;crc>>=1;if(mix)crc^=0x8c;value>>=1;}}
 return crc;
}
static int ds18Hex(char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1;}
static bool ds18Rom(const char* text,size_t length,uint8_t* rom){
 if(length!=16)return false;
 for(int i=0;i<8;i++){int a=ds18Hex(text[i*2]),b=ds18Hex(text[i*2+1]);if(a<0||b<0)return false;rom[i]=(a<<4)|b;}
 return rom[0]==0x28&&ds18Crc(rom,7)==rom[7];
}
struct DigitalTemperature {
 bool valid=false;float celsius=0;int raw=0;const char* fault="not_sampled";
};
static DigitalTemperature ds18Decode(const uint8_t* bytes,bool conversionIssued,float offset=0){
 DigitalTemperature out;
 if(!conversionIssued){out.fault="conversion_not_started";return out;}
 bool allHigh=true,allLow=true;for(int i=0;i<9;i++){if(bytes[i]!=0xff)allHigh=false;if(bytes[i]!=0)allLow=false;}
 if(allHigh||allLow){out.fault="sensor_not_present";return out;}
 if(ds18Crc(bytes,8)!=bytes[8]){out.fault="sensor_crc_error";return out;}
 if((bytes[4]&0x9f)!=0x1f){out.fault="sensor_configuration_error";return out;}
 int resolution=(bytes[4]>>5)&3;
 int raw=(int16_t)((uint16_t)bytes[0]|((uint16_t)bytes[1]<<8));
 int mask=(1<<(3-resolution))-1;raw&=~mask;out.raw=raw;
 if(raw==85*16){out.fault="power_on_or_85c";return out;}
 float temp=raw/16.0f;
 if(temp< -55||temp>125||!isfinite(offset)||offset< -30||offset>30||temp+offset< -55||temp+offset>125){out.fault="temperature_out_of_range";return out;}
 out.valid=true;out.celsius=temp+offset;out.fault="";return out;
}

// Runtime logic is shared with a fake bus in native tests. Conversions are
// addressed, overlap across probes, and never block for the 750 ms conversion.
struct DigitalTemperatureCycle {
 bool pending=false;uint64_t started=0;uint64_t attempted=0;bool attemptedOnce=false;
 void reset(){pending=false;started=attempted=0;attemptedOnce=false;}
 template<class Bus> bool tick(Bus &bus,const uint8_t* rom,uint64_t now,int sampleMs,float offset,DigitalTemperature &out){
  out=DigitalTemperature();
  if(pending){
   if(now-started<750)return false;
   pending=false;
   if(!bus.reset()){out.fault="sensor_not_present";return true;}
   bus.select(rom);bus.write(0xbe);uint8_t scratch[9];for(auto &value:scratch)value=bus.read();
   out=ds18Decode(scratch,true,offset);return true;
  }
  if(attemptedOnce&&now-attempted<(uint64_t)sampleMs)return false;
  attempted=now;attemptedOnce=true;
  if(!bus.reset()){out.fault="sensor_not_present";return true;}
  bus.select(rom);bus.write(0xb4);
  if(!bus.read_bit()){out.fault="parasite_power_unsupported";return true;}
  if(!bus.reset()){out.fault="sensor_not_present";return true;}
  bus.select(rom);bus.write(0x44,0);pending=true;started=now;return false;
 }
};
