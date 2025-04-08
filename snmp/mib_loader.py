from pysnmp.smi import builder, view, compiler
import os

# Инициализация билдера
mib_builder = builder.MibBuilder()

# Добавим папку для локального кеша MIB-файлов
local_mib_path = os.path.expanduser("~/.pysnmp/mibs")
if not os.path.exists(local_mib_path):
    os.makedirs(local_mib_path)

# Установка компилятора и онлайн-источника
compiler.addMibCompiler(
    mib_builder,
    sources=['http://mibs.snmplabs.com/asn1/@mib@'],
    destination=local_mib_path
)

# Обязательно добавить локальную директорию как источник
mib_builder.addMibSources(builder.DirMibSource(local_mib_path))

# Создаем MibViewController
mib_view = view.MibViewController(mib_builder)

# Загружаем нужные MIB'ы
try:
    mib_builder.loadModules('IF-MIB', 'SNMPv2-MIB', 'BRIDGE-MIB', 'RFC1213-MIB')
except Exception as e:
    print(f"⚠️ Ошибка загрузки MIB: {e}")
