#!/usr/bin/env python3

import argparse
import os

def generate_command(start_frequency, stop_frequency, step_size):
    base_command = "rtl_433 -d driver=sdrplay -t \"antenna=A\""
    frequency_command = []

    current_frequency = start_frequency
    while current_frequency <= stop_frequency:
        # Limit to 6 decimal places
        freq_str = f"{current_frequency:.6f}"
        frequency_command.append(f"-f {freq_str}M")
        current_frequency += step_size

    # Check if more than 32 frequencies are generated
    if len(frequency_command) > 32:
        achievable_stop_freq = start_frequency + (step_size * 31)  # 31 steps to allow start_frequency as the first
        
        # Calculate required step size to cover desired range with 32 steps
        required_step_size = (stop_frequency - start_frequency) / 31

        print("Warning: More than 32 frequencies generated.")
        print(f"a) With the provided step size of {step_size}M, you can achieve from {start_frequency}M to {achievable_stop_freq:.6f}M.")
        print(f"b) To achieve the full frequency range from {start_frequency}M to {stop_frequency}M, you'd need a step size of approximately {required_step_size:.6f}M.")
        
        exit(1)

    additional_options = "-H 15s -v"

    full_command = f"{base_command} {' '.join(frequency_command)} {additional_options}"
    return full_command

def main():
    parser = argparse.ArgumentParser(description="Generate and execute rtl_433 command with frequencies.")
    parser.add_argument("start_frequency", type=float, help="Starting frequency in MHz")
    parser.add_argument("stop_frequency", type=float, help="Stopping frequency in MHz")
    parser.add_argument("step_size", type=float, help="Step size in MHz")

    args = parser.parse_args()
    
    command = generate_command(args.start_frequency, args.stop_frequency, args.step_size)
    print(f"Executing: {command}")
    os.system(command)

if __name__ == "__main__":
    main()
