#pragma once
#include <math.h>
#include <stdint.h>

// State only: no history waveform buffers, allocations or hardware dependencies.
struct ContactInput {
 bool ready=false,candidate=false,active=false;
 uint64_t changedAt=0;
 bool sample(bool value,uint64_t now,uint32_t debounceMs){
  if(!ready){ready=true;candidate=active=value;changedAt=now;return false;}
  if(value!=candidate){candidate=value;changedAt=now;}
  if(candidate!=active&&now-changedAt>=debounceMs){active=candidate;return true;}
  return false;
 }
};
