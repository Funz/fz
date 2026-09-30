# Output File Structure

Each case creates a directory with complete execution metadata:

## `log.txt` - Execution Metadata
```
Command: bash calculate.sh input.txt
Exit code: 0
Time start: 2024-03-15T10:30:45.123456
Time end: 2024-03-15T10:32:12.654321
Execution time: 87.531 seconds
User: john_doe
Hostname: compute-01
Operating system: Linux
Platform: Linux-5.15.0-x86_64
Working directory: /tmp/fz_temp_abc123/case1
Original directory: /home/john/project
```

## `.fz_hash` - Input File Checksums
```
a1b2c3d4e5f6...  input.txt
f6e5d4c3b2a1...  config.dat
```

Used for cache matching.
