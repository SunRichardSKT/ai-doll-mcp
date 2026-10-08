#pragma once
#include <algorithm>
#include <stdint.h>

// Pure sampling statistics, shared by firmware and native algorithm tests.
struct PressureSamples {
 uint16_t values[512]={};
 int count=0;
 void reset(){count=0;}
 bool add(int raw){if(raw<0||raw>4095||count>=512)return false;values[count++]=raw;return true;}
 __attribute__((noinline)) int percentile(int percent) const {
  if(!count)return -1;
  uint16_t sorted[512];std::copy(values,values+count,sorted);std::sort(sorted,sorted+count);
  return sorted[(count-1)*percent/100];
 }
};
struct PressureThresholds {bool valid=false;int on=0,off=0;const char* reason="capture_all_stages";};
static __attribute__((noinline)) PressureThresholds pressureThresholds(const PressureSamples *stages){
 PressureThresholds r;
 for(int i=0;i<3;i++)if(stages[i].count<20){r.reason="too_few_samples";return r;}
 int baseline=stages[0].percentile(95),light=stages[1].percentile(20),gap=light-baseline;
 if(gap<64){r.reason="light_press_not_separated";return r;}
 if(stages[0].percentile(95)-stages[0].percentile(20)>gap/2){r.reason="baseline_unstable";return r;}
 if(stages[2].percentile(50)+32<stages[1].percentile(50)){r.reason="strong_press_below_light";return r;}
 if(stages[2].percentile(95)>=4080){r.reason="adc_saturated";return r;}
 r.off=baseline+gap/4;r.on=baseline+gap*3/5;r.valid=r.off<r.on&&r.on<=4095;r.reason=r.valid?"ok":"invalid_thresholds";return r;
}
