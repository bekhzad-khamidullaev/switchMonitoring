from pysnmp.smi import builder, view, compiler
import os

def init_mibs():
    mib_builder = builder.MibBuilder()

    local_path = os.path.expanduser("~/.pysnmp/mibs")
    os.makedirs(local_path, exist_ok=True)

    mib_builder.addMibSources(builder.DirMibSource(local_path))

    compiler.addMibCompiler(
        mib_builder,
        sources=['http://mibs.snmplabs.com/asn1/@mib@'],
        destination=local_path
    )

    mib_view = view.MibViewController(mib_builder)

    # Попробуем заранее подгрузить часто используемые
    try:
        mib_builder.loadModules('IF-MIB', 'SNMPv2-MIB', 'RFC1213-MIB', 'BRIDGE-MIB')
    except Exception as e:
        print(f"[!] MIB preload failed: {e}")

    return mib_view

# Это можно вызывать из tasks или celery.py
