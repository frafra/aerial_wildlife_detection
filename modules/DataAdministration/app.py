'''
    Bottle routings for data administration
    (i.e., image, annotation, and prediction
    down- and uploads).
    Needs to be run from instance responsible
    for serving files (i.e., FileServer module).

    2020 Benjamin Kellenberger
'''

import os
import datetime
from bottle import request, response, abort
from .backend.middleware import DataAdministrationMiddleware
from util.cors import enable_cors
from util import helpers



#TODO: HUGE PROBLEM: CORS FORBIDS COOKIE FORWARDING WITH WILDCARD ORIGIN, SO USER IS UNAUTHORIZED...


class DataAdministrator:

    def __init__(self, config, app):
        self.config = config
        self.app = app

        if not helpers.is_fileServer(config):
            raise Exception('DataAdministrator module must be run on file server instance.')

        self.middleware = DataAdministrationMiddleware(config)

        self.login_check = None
        self._initBottle()


    def loginCheck(self, project=None, admin=False, superuser=False, canCreateProjects=False, extend_session=False):
        return self.login_check(project, admin, superuser, canCreateProjects, extend_session)


    def addLoginCheckFun(self, loginCheckFun):
        self.login_check = loginCheckFun

    
    @staticmethod
    def _parse_range(params, paramName, minValue, maxValue):
        '''
            Parses "params" (dict) for a given keyword
            "paramName" (str), and expects a dict with
            keywords "min" and "max" there. One of the
            two may be missing, in which case the values
            of "minValue" and "maxValue" will be used.
            Returns a tuple of (min, max) values, or None
            if "paramName" is not in "params."
        '''
        if params is None or not paramName in params:
            return None
        entry = params[paramName].copy()
        if not 'min' in entry:
            entry['min'] = minValue
        if not 'max' in entry:
            entry['max'] = maxValue
        return (entry['min'], entry['max'])


    def _initBottle(self):

        ''' Image management functionalities '''
        @enable_cors
        @self.app.post('/<project>/listImages')
        def list_images(project):
            '''
                Returns a list of images and various properties
                and statistics (id, filename, viewcount, etc.),
                all filterable by date and value ranges.
            '''
            if not self.loginCheck(project=project, admin=True):
                abort(401, 'forbidden')
            
            # parse parameters
            now = helpers.current_time()
            params = request.json

            imageAddedRange = self._parse_range(params, 'imageAddedRange',
                                            datetime.time.min,
                                            now)
            lastViewedRange = self._parse_range(params, 'lastViewedRange',
                                            datetime.time.min,
                                            now)
            viewcountRange = self._parse_range(params, 'viewcountRange',
                                            0,
                                            1e9)
            numAnnoRange = self._parse_range(params, 'numAnnoRange',
                                            0,
                                            1e9)
            numPredRange = self._parse_range(params, 'numPredRange',
                                            0,
                                            1e9)
            orderBy = (params['orderBy'] if 'orderBy' in params else None)
            order = (params['order'].lower() if 'order' in params else None)
            limit = (params['limit'] if 'limit' in params else None)


            # get images
            result = self.middleware.listImages(project,
                                            imageAddedRange,
                                            lastViewedRange,
                                            viewcountRange,
                                            numAnnoRange,
                                            numPredRange,
                                            orderBy,
                                            order,
                                            limit)
            
            return {'response': result}


        @enable_cors
        @self.app.post('/<project>/uploadImages')
        def upload_images(project):
            '''
                Upload image files through UI.
            '''
            if not self.loginCheck(project=project, admin=True):
                abort(401, 'forbidden')
            
            try:
                images = request.files
                result = self.middleware.uploadImages(project, images)
                return {'result': result}
            except Exception as e:
                return {'status': 1, 'message': str(e)}


        # #TODO
        # @self.app.hook('after_request')
        # def cors_enabler():
        #     response.headers['Access-Control-Allow-Origin'] = 'http://kuduvm.westus2.cloudapp.azure.com:8088'
        #     response.headers['Access-Control-Allow-Credentials'] = 'true'
        #     response.headers['Access-Control-Allow-Methods'] = 'PUT, GET, POST, DELETE, OPTIONS'
        #     response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'


        @self.app.get('/<project>/scanForImages')
        @enable_cors
        def scan_for_images(project):
            '''
                Search project file directory on disk for
                images that are not registered in database.
            '''

            if not self.loginCheck(project=project, admin=True):
                abort(401, 'forbidden')

            result = self.middleware.scanForImages(project)
            return {'response': result}


        @enable_cors
        @self.app.post('/<project>/addExistingImages')
        def add_images(project):
            '''
                Add images that exist in project file directory
                on disk, but are not yet registered in database.
            '''
            if not self.loginCheck(project=project, admin=True):
                abort(401, 'forbidden')

            try:
                imageNames = request.json
                status, result = self.middleware.addExistingImages(project, imageNames['images'])
                return {'status': status, 'response': result}
            except Exception as e:
                return {'status': 1, 'message': str(e)}


        @enable_cors
        @self.app.post('/<project>/removeImages')
        def remove_images(project):
            '''
                Remove images from database, including predictions
                and annotations (if flag is set).
                Also remove images from disk (if flag is set).
            '''
            if not self.loginCheck(project=project, admin=True):
                abort(401, 'forbidden')
            
            try:
                data = request.json
                imageIDs = data['images']
                if 'forceRemove' in data:
                    forceRemove = data['forceRemove']
                else:
                    forceRemove = False
                if 'deleteFromDisk' in data:
                    deleteFromDisk = data['deleteFromDisk']
                else:
                    deleteFromDisk = False
                
                images_deleted = self.middleware.removeImages(project,
                                                            imageIDs,
                                                            forceRemove,
                                                            deleteFromDisk)
                
                return {'status': 0, 'images_deleted': images_deleted}

            except Exception as e:
                return {'status': 1, 'message': str(e)}


        ''' Annotation and prediction up- and download functionalities '''
        #TODO


        @enable_cors
        @self.app.get('/<project>/getValidImageExtensions')
        def get_valid_image_extensions(project=None):
            '''
                Returns the file extensions for images currently
                supported by AIDE.
            '''
            return {'extensions': helpers.valid_image_extensions}

        
        @enable_cors
        @self.app.get('/<project>/getValidMIMEtypes')
        def get_valid_mime_types(project=None):
            '''
                Returns the MIME types for images currently
                supported by AIDE.
            '''
            return {'MIME_types': helpers.valid_image_mime_types}

        
        # data download
        @enable_cors
        @self.app.post('/<project>/requestDownloads')
        def request_data_downloads(project):
            '''
                Parses request parameters and then assembles project-
                related metadata (annotations, predictions, etc.) by
                storing them as files on the server in a temporary
                directory.
                Returns the download links to those temporary files.
            '''
            #TODO: allow download for non-admins?
            if not self.loginCheck(project=project, admin=True):
                abort(401, 'forbidden')
            
            # parse parameters
            #TODO
