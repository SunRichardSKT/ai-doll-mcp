"""Manage only child processes recorded by this project, including Windows PID reuse checks."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import signal
import subprocess
import time


def _windows_handle(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000 | 0x0001 | 0x00100000, False, pid)
    return kernel, handle


def _windows_identity(kernel, handle):
    created, exited, system, user = (wintypes.FILETIME() for _ in range(4))
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
    if not kernel.GetProcessTimes(handle,ctypes.byref(created),ctypes.byref(exited),ctypes.byref(system),ctypes.byref(user)):
        return None
    exit_code = wintypes.DWORD()
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
    if not kernel.GetExitCodeProcess(handle,ctypes.byref(exit_code)) or exit_code.value!=259: return None
    buffer = ctypes.create_unicode_buffer(32768)
    size = wintypes.DWORD(len(buffer))
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    if not kernel.QueryFullProcessImageNameW(handle,0,buffer,ctypes.byref(size)): return None
    return dict(born=(created.dwHighDateTime<<32)|created.dwLowDateTime,
                executable=os.path.normcase(str(Path(buffer.value).resolve())))


def identity(pid):
    if type(pid) is not int or pid<=0: return None
    if os.name=='nt':
        kernel, handle = _windows_handle(pid)
        if not handle: return None
        try: return _windows_identity(kernel,handle)
        finally: kernel.CloseHandle(handle)
    try:
        stat = Path('/proc')/str(pid)/'stat'
        tail = stat.read_text().rsplit(')',1)[1].split()
        if tail[0]=='Z': return None
        return dict(born=tail[19],executable=str((Path('/proc')/str(pid)/'exe').resolve(strict=True)))
    except OSError: return None


def record(pid):
    value = identity(pid)
    if value is None: raise RuntimeError('Owned process exited before its identity could be recorded')
    return dict(pid=pid,**value)


def alive(value):
    return bool(value and identity(value.get('pid'))=={k:value.get(k) for k in ('born','executable')})


def launch(arguments, cwd):
    flags = subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    child = subprocess.Popen(arguments,cwd=cwd,stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
    try: return child, record(child.pid)
    except Exception:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
        raise


class OwnedChildJob:
    """A Windows supervisor's children die with it, even before a PID file is written."""
    def __init__(self):
        self.handle = None
        if os.name != 'nt':return
        class Basic(ctypes.Structure):
            _fields_ = [('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),
                        ('flags',wintypes.DWORD),('min_working',ctypes.c_size_t),('max_working',ctypes.c_size_t),
                        ('processes',wintypes.DWORD),('affinity',ctypes.c_size_t),
                        ('priority',wintypes.DWORD),('scheduling',wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name,ctypes.c_ulonglong) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
        class Limits(ctypes.Structure):
            _fields_ = [('basic',Basic),('io',IO),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),
                        ('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype=wintypes.HANDLE
        kernel.GetCurrentProcess.restype=wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.CreateJobObjectW(None,None)
        limits=Limits();limits.basic.flags=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if (not handle or not kernel.SetInformationJobObject(handle,9,ctypes.byref(limits),ctypes.sizeof(limits))
                or not kernel.AssignProcessToJobObject(handle,kernel.GetCurrentProcess())):
            if handle:kernel.CloseHandle(handle)
            raise RuntimeError('Cannot establish project child-process ownership')
        self.kernel,self.handle=kernel,handle

    def close(self):
        if self.handle:
            # Call only after private final status has been saved. This also ends the supervisor itself.
            self.kernel.CloseHandle(self.handle)
            self.handle=None


def terminate(value):
    if not value: return False
    if os.name=='nt':
        kernel,handle = _windows_handle(value.get('pid',0))
        if not handle: return False
        try:
            if _windows_identity(kernel,handle)!={k:value.get(k) for k in ('born','executable')}: return False
            kernel.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT]
            kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
            if not kernel.TerminateProcess(handle,0): return False
            kernel.WaitForSingleObject(handle,5000)
            return True
        finally: kernel.CloseHandle(handle)
    if not alive(value): return False
    os.kill(value['pid'],signal.SIGTERM)
    for _ in range(50):
        if not alive(value): return True
        time.sleep(.1)
    if alive(value): os.kill(value['pid'],signal.SIGKILL)
    return True
