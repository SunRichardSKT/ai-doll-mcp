#include "../firmware/src/digital_temperature.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include <array>
#include <vector>

static std::array<uint8_t,9> scratch(int raw,int resolution=3){
 std::array<uint8_t,9> bytes={{(uint8_t)raw,(uint8_t)(raw>>8),0x4b,0x46,(uint8_t)(0x1f|(resolution<<5)),0xff,0x0c,0x10,0}};
 bytes[8]=ds18Crc(bytes.data(),8);return bytes;
}
struct FakeWire {
 bool present=true,powered=true;int selected=0,readIndex=0,command=0,conversions=0;
 std::array<std::array<uint8_t,9>,2> data={{scratch(25*16),scratch(-10*16)}};
 std::vector<int> commands;
 bool reset(){readIndex=0;return present;}
 void select(const uint8_t* rom){selected=rom[1]&1;}
 void write(int value,int power=0){assert(power==0);command=value;commands.push_back(value);if(value==0x44)conversions++;}
 int read_bit(){return powered?1:0;}
 uint8_t read(){assert(command==0xbe&&readIndex<9);return data[selected][readIndex++];}
};
int main(){
 // CRC-8/MAXIM-DOW check value for the standard ASCII check vector.
 assert(ds18Crc((const uint8_t*)"123456789",9)==0xa1);
 uint8_t rom[8]={0x28,1,2,3,4,5,6,0};rom[7]=ds18Crc(rom,7);
 char text[17];for(int i=0;i<8;i++)snprintf(text+i*2,3,"%02X",rom[i]);uint8_t decoded[8];
 assert(ds18Rom(text,16,decoded)&&!memcmp(rom,decoded,8));
 assert(!ds18Rom(text,15,decoded));text[0]='g';assert(!ds18Rom(text,16,decoded));text[0]='2';text[15]=text[15]=='0'?'1':'0';assert(!ds18Rom(text,16,decoded));
 uint8_t other[8]={0x10};other[7]=ds18Crc(other,7);for(int i=0;i<8;i++)snprintf(text+i*2,3,"%02x",other[i]);assert(!ds18Rom(text,16,decoded));
 for(int raw:{-55*16,-10*16,0,25*16+8,125*16}){
  auto bytes=scratch(raw);auto result=ds18Decode(bytes.data(),true);
  assert(result.valid&&result.celsius==raw/16.0f&&result.raw==raw);
 }
 auto bytes=scratch(25*16);assert(!ds18Decode(bytes.data(),false).valid);
 bytes[0]^=1;assert(!strcmp(ds18Decode(bytes.data(),true).fault,"sensor_crc_error"));
 bytes=scratch(85*16);assert(!strcmp(ds18Decode(bytes.data(),true).fault,"power_on_or_85c"));
 bytes=scratch(126*16);assert(!ds18Decode(bytes.data(),true).valid);
 bytes=scratch(25*16);assert(ds18Decode(bytes.data(),true,1.5).celsius==26.5);
 assert(!ds18Decode(bytes.data(),true,NAN).valid);assert(!ds18Decode(bytes.data(),true,31).valid);
 bytes.fill(0xff);assert(!strcmp(ds18Decode(bytes.data(),true).fault,"sensor_not_present"));
 bytes.fill(0);assert(!strcmp(ds18Decode(bytes.data(),true).fault,"sensor_not_present"));
 for(int resolution=0;resolution<4;resolution++){
  bytes=scratch(25*16+7,resolution);auto value=ds18Decode(bytes.data(),true);
  assert(value.valid&&value.raw==((25*16+7)&~((1<<(3-resolution))-1)));
 }
 bytes=scratch(25*16);bytes[4]=0;bytes[8]=ds18Crc(bytes.data(),8);assert(!ds18Decode(bytes.data(),true).valid);
 FakeWire bus;DigitalTemperatureCycle cycle;DigitalTemperature value;
 assert(!cycle.tick(bus,rom,0,1000,0,value));assert(cycle.pending&&bus.conversions==1);
 assert(!cycle.tick(bus,rom,749,1000,0,value));assert(cycle.tick(bus,rom,750,1000,0,value));assert(value.valid&&value.celsius==-10);
 assert(!cycle.tick(bus,rom,999,1000,0,value));assert(!cycle.tick(bus,rom,1000,1000,0,value));assert(bus.conversions==2);
 cycle.reset();assert(!cycle.pending&&!cycle.attemptedOnce);
 bus.present=false;assert(cycle.tick(bus,rom,0,1000,0,value));assert(!value.valid&&!strcmp(value.fault,"sensor_not_present"));
 assert(!cycle.tick(bus,rom,999,1000,0,value));bus.present=true;bus.powered=false;
 assert(cycle.tick(bus,rom,1000,1000,0,value));assert(!value.valid&&!strcmp(value.fault,"parasite_power_unsupported"));
 bus.powered=true;cycle.reset();assert(!cycle.tick(bus,rom,0,1000,0,value));bus.present=false;
 assert(cycle.tick(bus,rom,750,1000,0,value)&&!value.valid);
 bus.present=true;DigitalTemperatureCycle left,right;uint8_t first[8]={0x28,0};
 assert(!left.tick(bus,first,0,1000,0,value));assert(!right.tick(bus,rom,0,1000,0,value));
 assert(left.tick(bus,first,750,1000,0,value)&&value.celsius==25);
 assert(right.tick(bus,rom,750,1000,0,value)&&value.celsius==-10);
 puts("PASS: DS18B20 ROM/CRC, signed values, resolution, faults, external power, timing, cancellation and concurrent probes");
}
