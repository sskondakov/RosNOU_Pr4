import os
import uuid
import configparser
import patoolib
import time

script_path = os.path.dirname(os.path.abspath(__file__))

zip_base_path = os.path.join(script_path, 'amd64', 'Lib', 'site-packages.zip')
extract_path = os.path.dirname(zip_base_path)

def merge_multivolume_archive(base_path):
    output_path = base_path
    volume_num = 1
    
    first_volume = f'{base_path}.{volume_num:03d}'
    if not os.path.exists(first_volume):
        print(f'Первый том архива не найден: {first_volume}')
        return None
    
    print('Объединение томов архива...')
    with open(output_path, 'wb') as output_file:
        while True:
            volume_path = f'{base_path}.{volume_num:03d}'
            if not os.path.exists(volume_path):
                break
            
            print(f'Добавление тома {volume_num}: {volume_path}')
            with open(volume_path, 'rb') as volume_file:
                output_file.write(volume_file.read())
            
            volume_num += 1
    
    print(f'\nАрхив объединен: {output_path}')
    return output_path

# Объединяем архив, если он многотомный
if os.path.exists(f"{zip_base_path}.001"):
    merged_archive = merge_multivolume_archive(zip_base_path)
    
    if merged_archive:
        print('\nРаспаковка архива...')
        patoolib.extract_archive(merged_archive, outdir=extract_path)
        
        time.sleep(5)
        try
            os.remove(merged_archive)
        except
            pass
        
        print('\nРаспаковка завершена.')
        
else:
    if os.path.exists(zip_base_path):
        print('\nРаспаковка архива...')
        patoolib.extract_archive(zip_base_path, outdir=extract_path)
        print('\nРаспаковка завершена.')

    else:
        print(f'\nАрхив не найден: {zip_base_path}')

config_path = os.path.join(script_path, 'gigakeys.ini')

if not os.path.exists(config_path):
    config = configparser.ConfigParser()

    config.add_section('GIGACHAT')
    config.set('GIGACHAT', 'authorization_key', '')
    config.set('GIGACHAT', 'session_id', str(uuid.uuid4()))

    with open(config_path, 'w', encoding='utf-8') as config_file:
        config.write(config_file)

print('''\nПрограмма успешно установлена.

Укажите ключ авторизации GigaChat в файле gigakeys.ini.'''
)