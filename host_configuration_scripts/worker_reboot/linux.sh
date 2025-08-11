echo "Running Host Configuration script to reboot this worker." \
     "If already rebooted, start processing steps." \
     "Otherwise, reboot"
ls /var/lib/deadline
if [ -f /var/lib/deadline/rebooted ]; then
    echo "Host already Rebooted, ready to start."
    exit 0
fi
echo "Host has not been rebooted."
# Caution When changing this file or path.
# If the file cannot be created properly a worker can be stuck in a rebooting loop.
touch /var/lib/deadline/rebooted
# Optional chmod, use 660 if jobs need to check if this host is configured.
chmod 660 /var/lib/deadline/rebooted
echo "Marker file created, Rebooting worker host."
sudo reboot now
sleep 60
exit 1