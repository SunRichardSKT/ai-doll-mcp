#include "../firmware/src/pressure_calibration.h"
#include <cassert>
#include <iostream>
#include <cstring>
static void fill(PressureSamples &s,int center,int count=100){for(int i=0;i<count;i++)assert(s.add(center+i%9-4));}
int main(){
 PressureSamples stages[3];fill(stages[0],120);fill(stages[1],700);fill(stages[2],1800);
 auto r=pressureThresholds(stages);assert(r.valid&&r.off>124&&r.on>r.off&&r.on<696);
 // A few spikes must not destroy otherwise separated pressure distributions.
 stages[0].values[0]=4095;stages[1].values[0]=0;r=pressureThresholds(stages);assert(r.valid);
 PressureSamples missing[3];fill(missing[0],100);assert(!pressureThresholds(missing).valid);
 PressureSamples weak[3];fill(weak[0],100);fill(weak[1],125);fill(weak[2],150);assert(!pressureThresholds(weak).valid);
 PressureSamples reversed[3];fill(reversed[0],100);fill(reversed[1],700);fill(reversed[2],300);assert(!pressureThresholds(reversed).valid);
 PressureSamples saturated[3];fill(saturated[0],100);fill(saturated[1],700);fill(saturated[2],4090);assert(!pressureThresholds(saturated).valid);
 PressureSamples jitter[3];for(int i=0;i<100;i++)jitter[0].add(i*3);fill(jitter[1],400);fill(jitter[2],1000);assert(!pressureThresholds(jitter).valid);
 PressureSamples bounds;assert(!bounds.add(-1)&&!bounds.add(4096));for(int i=0;i<512;i++)assert(bounds.add(i));assert(!bounds.add(5));
 assert(bounds.percentile(20)==102&&bounds.percentile(95)==485);
 std::cout<<"PASS: separated thresholds, spike tolerance, missing/weak/reversed/saturated/unstable samples, buffer bounds\n";
}
