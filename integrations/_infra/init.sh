if test -e /usr/local/share/ca-certificates/cert.crt; then
  update-ca-certificates
fi

# delete output file if exists
MEMRAY_OUTPUT_FILE=/var/memray/output.bin

rm -f $MEMRAY_OUTPUT_FILE

memray run --trace-python-allocators -o $MEMRAY_OUTPUT_FILE debug.py