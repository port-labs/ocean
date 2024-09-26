if test -e /usr/local/share/ca-certificates/cert.crt; then
  update-ca-certificates
fi

memray run --trace-python-allocators debug.py