# ism_wardriving

Code to collect, analyze, and map ISM band sensor data in public spaces with a Raspberry Pi and cheap software defined receivers (SDRs).

I've tried to be complete, but there may be errors and ommission, so the code is provided as is.

Provided open source under the [MIT License](https://github.com/dirkbeer/ism_wardriving/raw/main/LICENSE)

Copyright ©2023 Dirk Beer

![image](https://github.com/dirkbeer/ism_wardriving/assets/6425332/f6749998-d859-4517-8c3e-d1680a7926e5)

## Scripts:

_rtl.py_ - receives sensor data from rtl_433 and gpsd and writes it to a time-stamped csv data file

_map.py_ - reads data file, extracts a list of unique sensors, serves reading location in web map

_systemd/rtl.service_ - systemd script to run _rtl_433_gps.py_ at boot

_systemd/gpsd.service_ - systemd script to run the locally compiled gspd because the scons udev-install does not seem to work

## Software:
* SDRplay API
* rtl-sdr debian package
* rtl-433 debian package
* gpsd (installed from source to avoid bug in debian package)

## Hardware:
* Raspberry Pi 4
* Good SD card, like SanDisk 64GB High Endurance Video MicroSDXC Card or Samsung PRO Endurance 64GB 100MB/s (U1) MicroSDXC Memory Card
* RTL-SDR USB dongles OR Soapy-enabled receiver such as SDRplay RSP 2
* VK-162 G-Mouse USB GPS Dongle

## Antennas:
* 70cm or dual-band 2m / 70cm ham antennas work well for 433MHz ISM band
* Helium / LoRaWAN antennas work for 915MHz ISM band

## Installation:
1. Install Raspberry Pi OS using the Raspberry Pi imager
   
   a. Raspberry Pi OS Lite (32-bit)
   
   b. Set hostname
   
   c. Enable SSH with password authentication
   
   d. Set username and password (type carefully when entering the password since you can't see the letters)
   
   e. Configure wireless LAN, including country
   
   f. Set locale settings

   g. When done, put the SD card in the RPi, power it on, wait for ~3 minutes for it to boot, and then ssh into it (replace username and hostname with what you set earlier).
   ```
   ssh username@hostname.local
   ```
3. Expand the filesystem, force use of 32-bit, reboot to make effective. `lscpu` should indicate 32-bit
   ```
   sudo raspi-config --expand-rootfs
   echo "arm_64bit=0" | sudo tee -a /boot/config.txt
   sudo reboot
   lscpu
   ```
4. Update the system
   ```
   sudo apt update -y && sudo apt full-upgrade -y
   ```
5. (only if using an SDRplay device) Install the SDRplay API and Soapy with SDRplay support using the build scripts. Say yes to lsusb and no to rebooting after the API install. Ignore warnings when building Soapy.
   ```
   wget https://www.sdrplay.com/software/SDRplay_RPi_Scripts_v0.3.zip
   unzip SDRplay_RPi_Scripts_v0.3.zip -d SDRplay_RPi_Scripts
   cd SDRplay_RPi_Scripts
   ./1installAPI.sh
   ./2buildSoapy.sh
   sudo reboot
   SoapySDRUtil --find="driver=sdrplay"
   SoapySDRUtil --probe="driver=sdrplay"
   ```
4. Install rtl-sdr and rtl-433
   ```
   sudo apt install rtl-sdr rtl-433
   ```
   or if using an SDRplay device, or you want the latest sensor support, build rtl-433 from source (recommended, apt package seems to be broken)
   ```
   sudo apt purge rtl-433 && hash -r
   git clone https://github.com/merbanan/rtl_433.git
   sudo apt-get install libtool libusb-1.0-0-dev librtlsdr-dev rtl-sdr build-essential cmake pkg-config libsoapysdr-dev libssl-dev
   cd rtl_433/
   mkdir build
   cd build
   cmake -DENABLE_SOAPYSDR=ON ..
   make
   sudo make install
   ```
6. Test rtl-433; by default will run at 433.91MHz which is most likely place to receive sensors
   ```
   rtl_433
   ```
   or if using Soapy (for example with the SDRplay device)
   ```
   rtl_433 -d driver=sdrplay -t "antenna=A"
   ```
9. Install gpsd
  
   a. Build gpsd from source to enable use of GPS. If you use the package you just get a bunch of identical lat longs (spend a lot of time figuring this out, including talking to Gary E Miller himself. https://gpsd.gitlab.io/gpsd/building.html
   ```
   sudo -i
   apt purge gpsd
   apt install scons libncurses5-dev python3-dev pps-tools git
   # ln -s /usr/bin/python3 /usr/bin/python
   wget https://download.savannah.gnu.org/releases/gpsd/gpsd-3.25.zip
   unzip ./gpsd-3.25.zip
   cd gpsd-3.25
   scons && scons check
   ```
   b. Install gpsd but do not use udev-install, it does not work to automatically determine the USB device.
   ```
   scons install
   echo 'PYTHONPATH="/usr/local/lib/python3/dist-packages"' | sudo tee -a /etc/environment
   ```
   c. Disable the default gpsd systemd scripts if any are present
   ```
   systemctl list-units --type=service --all | grep gps
   systemctl disable gps???
   systemctl stop gps???
   systemctl mask gps???
   ```
10. Install ism_wardriving and systemd service scripts
   ```
   git clone https://github.com/dirkbeer/ism_wardriving
   cd ism_wardriving
   sudo cp ./systemd/gpsd.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable gpsd.service
   ```
11. Plug in the GPS dongle if you haven't already, start the gpsd service, and test it
   ```
   sudo systemctl start gpsd.service
   sudo systemctl status gpsd.service   
   gpspipe -w
   ```
10. Set up rtl.py
   
    a. Install prerequisites
    ```
    sudo apt install python3-pip
    pip install psutil paho-mqtt 
    ```
    b. If desired, configure an MQTT server to send data to by renaming the `mqtt_config.json.template` to `mqtt_config.json` and filling in the appropriate details

    c. Configure the rtl script by editing one of the `.conf` file, and then specify that file at the top of `rtl.py`

    d. Test run `rtl.py`, replace the data file name below with the most recent one in the data folder
    ```
    ./rtl.py &
    ls -alt ./data
    tail -f ./data/rtl_433.92M_20230914_191114.json
    ```
13. Stop `rtl.py` using `fg` to bring it to the foreground, then Ctrl-c. Then start the rtl service and test again
    ```
    sudo cp ./systemd/rtl.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable rtl.service
    sudo systemctl start rtl.service
    sudo systemctl status rtl.service 
    ls -alt ./data
    tail -f ./data/rtl_433.92M_20230914_192123.json
    ```
14. Look at the output data using `map.py`. This will display summary statistics and serve a local map

## Notes

* Restart rtl at midnight every night to have daily logs
```
sudo crontab -e
0 0 * * * /usr/bin/systemctl restart rtl
```
* Scanning multiple frequencies
```
rtl_433 -d driver=sdrplay -t "antenna=A" -f 913.8M -f 914.0M -f 914.2M -f 914.4M -f 914.8M -f 915.0M -f 915.2M -f 915.4M -f 915.8M -f 916.0M -f 916.2M -H 15s -v
```
* Setting additional Soapy parameters for the SDRplay
```
rtl_433 -d driver=sdrplay -t "antenna=A,bandwith=8000000,sample_rate=10000000" -v
```
* Troubleshooting the SDRPlay API and Soapy
```
restartSDRplay
SoapySDRUtil --probe=driver=sdrplay
rtl_433 -d driver=sdrplay -f 915M -t "antenna=A" -F csv:log.csv
tail -f ./log.csv
```
* Output to syslog port
```
rtl_433 -d driver=sdrplay -f 915M -t "antenna=A" -F syslog::1514
nc -l -u -p 1514
```
* Disable laptop lid sensor in this file (when running on a laptp instead of RPi)
```
sudo gedit /etc/UPower/UPower.conf
```



