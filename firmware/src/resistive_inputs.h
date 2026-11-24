#pragma once
#include <math.h>
#include <stdint.h>

static constexpr float NTC_DEFAULT_BETA=3950;
struct NtcOptions {
 float r25=10000,beta=NTC_DEFAULT_BETA,pullDown=10000,series=4700,supplyMv=3300,offset=0,delta=1;
 int reportMs=30000;
};
// Board topology: supply -> series -> probe -> ADC -> pullDown -> GND.
static inline bool ntcTemperature(float mv,const NtcOptions &o,float &temperature){
 if(!isfinite(mv)||mv<20||mv>=o.supplyMv-20)return false;
 float resistance=o.pullDown*(o.supplyMv/mv-1)-o.series;
 if(!isfinite(resistance)||resistance<100)return false;
 temperature=1/(1/298.15f+logf(resistance/o.r25)/o.beta)-273.15f+o.offset;
 return isfinite(temperature)&&temperature>=-20&&temperature<=80;
}
struct TemperatureInput {
 bool ready=false;float reported=0;uint64_t reportedAt=0;
 bool sample(float value,uint64_t now,const NtcOptions &o){
  if(!ready||fabsf(value-reported)>=o.delta||now-reportedAt>=(uint32_t)o.reportMs){
   ready=true;reported=value;reportedAt=now;return true;
  }return false;
 }
};
struct WetOptions {int holdMs=600,dryMs=1000,pressureChannel=0;};
struct WetInput {
 bool wet=false,emitted=false,rising=false,falling=false;
 uint64_t since=0,drySince=0;
 // Bits: wet confirmed, one wipe per wet episode, dry confirmed.
 uint8_t sample(int raw,int on,int off,bool pressed,uint64_t now,const WetOptions &o){
  uint8_t events=0;
  if(raw>=on){if(!rising){rising=true;since=now;}falling=false;
   if(!wet&&now-since>=(uint32_t)o.holdMs){wet=true;events|=1;}}
  else if(raw<=off){rising=false;
   if(!falling){falling=true;drySince=now;}
   if(wet&&now-drySince>=(uint32_t)o.dryMs){wet=false;emitted=false;events|=4;}}
  else {rising=false;falling=false;}
  if(wet&&raw>off&&pressed&&!emitted){emitted=true;events|=2;}
  return events;
 }
};
