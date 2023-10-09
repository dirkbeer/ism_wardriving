#!/usr/bin/env python3

import subprocess

result = subprocess.run(['rtl_433','-R','help'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
output = result.stderr
lines = output.splitlines()

# Open the file in write mode
with open('protocols.conf', 'w') as file:
    for line in lines:
        if line.strip().startswith('[') and 'TPMS' not in line:
            start_index = line.find('[') + 1
            end_index = line.find(']')
            content_between_brackets = line[start_index:end_index]
            # Write to the file instead of printing
            file.write(f'protocol {content_between_brackets}\n')
