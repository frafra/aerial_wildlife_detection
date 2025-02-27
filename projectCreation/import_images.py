'''
    Helper function that imports a set of unlabeled images into the database.
    Works recursively (i.e., with images in nested folders) and different file
    formats and extensions (.jpg, .JPEG, .png, etc.).
    Skips images that have already been added to the database.

    Using this script requires the following steps:
    1. Make sure your images are of common format and readable by the web
       server (i.e., convert camera RAW images first).
    2. Copy your image folder into the FileServer's root file directory (i.e.,
       corresponding to the path under "staticfiles_dir" in the configuration
       *.ini file).
    3. Call the script from the AIDE code base on the FileServer instance.

    2019-21 Benjamin Kellenberger
'''

import os
import argparse
from psycopg2 import sql
from util.helpers import VALID_IMAGE_EXTENSIONS, listDirectory


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Import images into database.')
    parser.add_argument('--project', type=str,
                    help='Shortname of the project to insert the images into.')
    parser.add_argument('--settings_filepath', type=str, default='config/settings.ini', const=1, nargs='?',
                    help='Manual specification of the directory of the settings.ini file; only considered if environment variable unset (default: "config/settings.ini").')
    args = parser.parse_args()
    

    # setup
    print('Setup...')
    if not 'AIDE_CONFIG_PATH' in os.environ:
        os.environ['AIDE_CONFIG_PATH'] = str(args.settings_filepath)

    from tqdm import tqdm
    import datetime
    from util.configDef import Config
    from modules import Database

    currentDT = datetime.datetime.now()
    currentDT = '{}-{}-{} {}:{}:{}'.format(currentDT.year, currentDT.month, currentDT.day, currentDT.hour, currentDT.minute, currentDT.second)

    config = Config()
    dbConn = Database(config)
    if not dbConn.canConnect():
        raise Exception('Error connecting to database.')
    project = args.project


    # check if running on file server
    imgBaseDir = config.getProperty('FileServer', 'staticfiles_dir')
    if not os.path.isdir(imgBaseDir):
        raise Exception(f'"{imgBaseDir}" is not a valid directory on this machine. Are you running the script from the file server?')

    if not imgBaseDir.endswith(os.sep):
        imgBaseDir += os.sep

    
    # locate all images and their base names
    print('Locating image paths...')
    imgs = set()
    imgFiles = listDirectory(imgBaseDir, recursive=True)    #glob.glob(os.path.join(imgBaseDir, '**'), recursive=True)  #TODO: check if correct
    imgFiles = list(imgFiles)
    for i in tqdm(imgFiles):
        if os.path.isdir(i):
            continue
        
        _, ext = os.path.splitext(i)
        if ext.lower() not in VALID_IMAGE_EXTENSIONS:
            continue

        baseName = i.replace(imgBaseDir, '')
        imgs.add(baseName)

    # ignore images that are already in database
    print('Filter images already in database...')
    imgs_existing = dbConn.execute(sql.SQL('''
        SELECT filename FROM {};
    ''').format(sql.Identifier(project, 'image')), None, 'all')
    if imgs_existing is not None:
        imgs_existing = set([i['filename'] for i in imgs_existing])
    else:
        imgs_existing = set()

    imgs = list(imgs.difference(imgs_existing))
    imgs = [(i,) for i in imgs]

    # push image to database
    print('Adding to database...')
    dbConn.insert(sql.SQL('''
        INSERT INTO {} (filename)
        VALUES %s;
    ''').format(sql.Identifier(project, 'image')),
    imgs)

    print('Done.')