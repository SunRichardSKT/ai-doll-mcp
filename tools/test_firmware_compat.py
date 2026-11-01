"""Compile production simulation state/timers; no physical board or saved data."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class FirmwareCompatibilityTests(unittest.TestCase):
    def test_legacy_status_uses_event_state_and_single_release_timer(self):
        production=(ROOT/'firmware/src/touch_events.h').read_text(encoding='utf-8')
        inject=production[production.index('static void touchInject('):production.index('static void applyInputEnabled(')]
        # Only the transient/timer portion; ADC sampling is not part of this test.
        tick=production[production.index('static void touchTick(){'):production.index(' static uint64_t sampled=0;')]+'}\n'
        fixture=r'''
#include <cassert>
#include <cstdint>
#include <string>
#include <vector>
static constexpr int MAX_CHANNELS=4;
enum class DeviceKind { PRESSURE, LIGHT };
enum class ChannelDriver { SIMULATION };
struct ChannelConfig {DeviceKind kind=DeviceKind::PRESSURE;ChannelDriver driver=ChannelDriver::SIMULATION;std::string name="head";};
struct TouchState {bool active=false,simulated=true;uint32_t id=0;uint64_t started=0,deadline=0;int raw=0,peak=0;std::string body,driver;};
struct Reading {bool sampled=false,valid=false;float value=0;int raw=0;uint64_t at=0;std::string source,fault;};
struct OutputState {bool active=false,expired=false,physical=false;uint64_t deadline=0,started=0;int pwm=0,periodMs=0,intensity=0,lightPattern=0;};
static ChannelConfig channels[MAX_CHANNELS];static TouchState touches[MAX_CHANNELS];static Reading readings[MAX_CHANNELS];static OutputState outputs[MAX_CHANNELS];
static uint32_t touchSeq=0;static uint64_t clockNow=0;static uint64_t touchNow(){return clockNow;}
static const char* driverName(ChannelDriver){return "simulation";}
struct Event {int ch;bool ended;};static std::vector<Event> events;
static void touchEmit(int ch,bool ended){events.push_back({ch,ended});++touchSeq;}
struct {bool capturing=false,engaged=false;uint64_t deadline=0,expires=0;std::string error;}calibration;
static void stopOutput(int ch){outputs[ch].active=false;}
static void ledcWrite(int,int){}
static int lightDuty(uint64_t,int,int,int){return 0;}
'''
        checks=r'''
int main(){
 assert(activeSimulatedPressure()==-1);
 touchInject(0,1800);assert(activeSimulatedPressure()==0&&touches[0].raw==1800&&events.size()==1);
 clockNow=100;touchInject(1,2500);assert(activeSimulatedPressure()==1);
 touchInject(1,0);assert(activeSimulatedPressure()==0); // Other held channels remain visible.
 touchInject(2,2200,false);assert(activeSimulatedPressure()==0); // Real presses are not simulation.
 clockNow=4999;touchTick();assert(activeSimulatedPressure()==0);
 clockNow=5000;touchTick();assert(activeSimulatedPressure()==-1);
 assert(touches[2].active); // Simulation expiry cannot release a physical touch.
 size_t count=events.size();touchTick();touchInject(0,0);assert(events.size()==count);
 touchSeq=0xfffffffeU;clockNow=6000;touchInject(0,1500);touchInject(1,1700);
 assert(activeSimulatedPressure()==1); // Sequence rollover still picks the newest press.
 clockNow=11000;touchTick();assert(activeSimulatedPressure()==-1);
 count=events.size();clockNow=12000;touchTick();assert(events.size()==count);
}
'''
        with tempfile.TemporaryDirectory(prefix='aidoll-compat-') as folder:
            work=Path(folder);program=work/'compat.cpp';binary=work/'compat.exe'
            program.write_text(fixture+inject+tick+checks,encoding='utf-8')
            result=subprocess.run([shutil.which('g++') or 'g++','-std=c++11',str(program),'-o',str(binary)],capture_output=True,timeout=40)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
            result=subprocess.run([str(binary)],capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))

if __name__=='__main__':unittest.main()
