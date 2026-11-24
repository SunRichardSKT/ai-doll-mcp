"""Execute the production USB sampling branch with deterministic GPIO/ADC pins."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class FactoryProbeTests(unittest.TestCase):
    def test_samples_all_ports_and_restores_mux_without_changing_input_state(self):
        source=(ROOT/'firmware/src/lab_main.cpp').read_text(encoding='utf-8')
        start=source.index(' else if(cmd=="factory_sample"){')+len(' else if(cmd=="factory_sample"){')
        end=source.index('\n else if(cmd=="events")',start)
        body=source[start:end].rsplit('}',1)[0]
        fixture=r'''
#include <ArduinoJson.h>
#include <cassert>
#include <string>
static bool otaActive=false,otaCommitted=false,sensorEnabled=false;
static struct {bool engaged=false;} calibration;
static const char *apName="test-device",*touchBoot="test-boot";
static constexpr int OUTPUT=1,INPUT=0,ADC_11db=3;
static int pins[8]={},modes[8]={},reads=0,resolution=0,attenuation=0;
static int digitalRead(int p){return pins[p];}
static void digitalWrite(int p,int v){pins[p]=v;}
static void pinMode(int p,int v){modes[p]=v;}
static void analogReadResolution(int v){resolution=v;}
static void analogSetPinAttenuation(int p,int v){assert(p==0);attenuation=v;}
static void delayMicroseconds(int){}
static unsigned long millis(){return 1234;}
static int analogRead(int p){
 assert(p==0&&modes[3]==OUTPUT&&modes[4]==OUTPUT&&modes[5]==OUTPUT);
 ++reads;return 50+100*(pins[3]+2*pins[4]+4*pins[5]);
}
void probe(JsonDocument &out){
'''
        checks=r'''
}
int main(){
 JsonDocument out;probe(out);assert(!sensorEnabled&&reads==40);
 assert(resolution==12&&attenuation==ADC_11db);
 assert(modes[3]==INPUT&&modes[4]==INPUT&&modes[5]==INPUT);
 assert(out["raw"].size()==8&&out["source"]=="sensor");
 for(int i=0;i<8;i++)assert(out["raw"][i]==50+i*100);
 sensorEnabled=true;modes[3]=modes[4]=modes[5]=OUTPUT;
 pins[3]=1;pins[4]=0;pins[5]=1;out.clear();probe(out);
 assert(sensorEnabled&&pins[3]==1&&pins[4]==0&&pins[5]==1);
 assert(modes[3]==OUTPUT&&modes[4]==OUTPUT&&modes[5]==OUTPUT);
 reads=0;otaActive=true;out.clear();probe(out);
 assert(reads==0&&!out["error"].isNull()&&out["raw"].isNull());
 otaActive=false;calibration.engaged=true;out.clear();probe(out);
 assert(reads==0&&!out["error"].isNull());
}
'''
        with tempfile.TemporaryDirectory(prefix='doll-probe-') as temporary:
            work=Path(temporary);cpp=work/'probe.cpp';exe=work/'probe.exe'
            cpp.write_text(fixture+body+checks,encoding='utf-8')
            include=ROOT/'firmware/.pio/libdeps/supermini-lab/ArduinoJson/src'
            result=subprocess.run([shutil.which('g++') or 'g++','-std=c++17','-I',str(include),str(cpp),'-o',str(exe)],capture_output=True,timeout=40)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
            result=subprocess.run([str(exe)],capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))

if __name__=='__main__':unittest.main()
