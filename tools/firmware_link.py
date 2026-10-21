"""Keep the application within the existing OTA partition without moving data."""
Import('env')
env.Append(LINKFLAGS=['-flto', '-fuse-linker-plugin'])
