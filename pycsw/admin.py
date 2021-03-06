# -*- coding: ISO-8859-15 -*-
# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@hotmail.com>
#
# Copyright (c) 2012 Tom Kralidis
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================

import logging
import os
import sys
from glob import glob

from lxml import etree
from pycsw import metadata, repository, util

LOGGER = logging.getLogger(__name__)


def setup_db(database, table, home, create_sfsql_tables=True, create_plpythonu_functions=True, extra_columns=[]):
    """Setup database tables and indexes"""
    from sqlalchemy import Column, create_engine, Integer, String, MetaData, \
        Table, Text

    LOGGER.info('Creating database %s', database)
    dbase = create_engine(database)

    mdata = MetaData(dbase)

    if create_sfsql_tables:
        LOGGER.info('Creating table spatial_ref_sys')
        srs = Table(
            'spatial_ref_sys', mdata,
            Column('srid', Integer, nullable=False, primary_key=True),
            Column('auth_name', String(256)),
            Column('auth_srid', Integer),
            Column('srtext', String(2048))
        )
        srs.create()
    
        i = srs.insert()
        i.execute(srid=4326, auth_name='EPSG', auth_srid=4326, srtext='GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.01745329251994328,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]')
    
        LOGGER.info('Creating table geometry_columns')
        geom = Table(
            'geometry_columns', mdata,
            Column('f_table_catalog', String(256), nullable=False),
            Column('f_table_schema', String(256), nullable=False),
            Column('f_table_name', String(256), nullable=False),
            Column('f_geometry_column', String(256), nullable=False),
            Column('geometry_type', Integer),
            Column('coord_dimension', Integer),
            Column('srid', Integer, nullable=False),
            Column('geometry_format', String(5), nullable=False),
        )
        geom.create()
    
        i = geom.insert()
        i.execute(f_table_catalog='public', f_table_schema='public',
                  f_table_name=table, f_geometry_column='wkt_geometry',
                  geometry_type=3, coord_dimension=2,
                  srid=4326, geometry_format='WKT')

    # abstract metadata information model

    LOGGER.info('Creating table %s', table)
    records = Table(
        table, mdata,
        # core; nothing happens without these
        Column('identifier', String(256), primary_key=True),
        Column('typename', String(32),
               default='csw:Record', nullable=False, index=True),
        Column('schema', String(256),
               default='http://www.opengis.net/cat/csw/2.0.2', nullable=False,
               index=True),
        Column('mdsource', String(256), default='local', nullable=False,
               index=True),
        Column('insert_date', String(20), nullable=False, index=True),
        Column('xml', Text, nullable=False),
        Column('anytext', Text, nullable=False),
        Column('language', String(32), index=True),

        # identification
        Column('type', String(128), index=True),
        Column('title', String(2048), index=True),
        Column('title_alternate', String(2048), index=True),
        Column('abstract', String(2048), index=True),
        Column('keywords', String(2048), index=True),
        Column('keywordstype', String(256), index=True),
        Column('parentidentifier', String(32), index=True),
        Column('relation', String(256), index=True),
        Column('time_begin', String(20), index=True),
        Column('time_end', String(20), index=True),
        Column('topicategory', String(32), index=True),
        Column('resourcelanguage', String(32), index=True),

        # attribution
        Column('creator', String(256), index=True),
        Column('publisher', String(256), index=True),
        Column('contributor', String(256), index=True),
        Column('organization', String(256), index=True),

        # security
        Column('securityconstraints', String(256), index=True),
        Column('accessconstraints', String(256), index=True),
        Column('otherconstraints', String(256), index=True),

        # date
        Column('date', String(20), index=True),
        Column('date_revision', String(20), index=True),
        Column('date_creation', String(20), index=True),
        Column('date_publication', String(20), index=True),
        Column('date_modified', String(20), index=True),

        Column('format', String(128), index=True),
        Column('source', String(1024), index=True),

        # geospatial
        Column('crs', String(256), index=True),
        Column('geodescode', String(256), index=True),
        Column('denominator', Integer, index=True),
        Column('distancevalue', Integer, index=True),
        Column('distanceuom', String(8), index=True),
        Column('wkt_geometry', Text),

        # service
        Column('servicetype', String(32), index=True),
        Column('servicetypeversion', String(32), index=True),
        Column('operation', String(256), index=True),
        Column('couplingtype', String(8), index=True),
        Column('operateson', String(32), index=True),
        Column('operatesonidentifier', String(32), index=True),
        Column('operatesoname', String(32), index=True),

        # additional
        Column('degree', String(8), index=True),
        Column('classification', String(32), index=True),
        Column('conditionapplyingtoaccessanduse', String(256), index=True),
        Column('lineage', String(32), index=True),
        Column('responsiblepartyrole', String(32), index=True),
        Column('specificationtitle', String(32), index=True),
        Column('specificationdate', String(20), index=True),
        Column('specificationdatetype', String(20), index=True),

        # distribution
        # links: format "name,description,protocol,url[^,,,[^,,,]]"
        Column('links', Text, index=True),
    )

    # add extra columns that may have been passed via extra_columns
    # extra_columns is a list of sqlalchemy.Column objects
    if extra_columns:
        LOGGER.info('Extra column definitions detected')
        for extra_column in extra_columns:
            LOGGER.info('Adding extra column: %s', extra_column)
            records.append_column(extra_column)

    records.create()

    if create_plpythonu_functions:
        if dbase.name == 'postgresql':  # create plpythonu functions within db
            LOGGER.info('Setting plpythonu functions')
            pycsw_home = home
            conn = dbase.connect()
            function_query_spatial = '''
        CREATE OR REPLACE FUNCTION query_spatial(bbox_data_wkt text, bbox_input_wkt text, predicate text, distance text)
        RETURNS text
        AS $$
            import sys
            sys.path.append('%s')
            from pycsw import util
            return util.query_spatial(bbox_data_wkt, bbox_input_wkt, predicate, distance)
            $$ LANGUAGE plpythonu;
        ''' % pycsw_home
            function_update_xpath = '''
        CREATE OR REPLACE FUNCTION update_xpath(xml text, recprops text)
        RETURNS text
        AS $$
            import sys
            sys.path.append('%s')
            from pycsw import util
            return util.update_xpath(xml, recprops)
            $$ LANGUAGE plpythonu;
        ''' % pycsw_home
            conn.execute(function_query_spatial)
            conn.execute(function_update_xpath)


def load_records(context, database, table, xml_dirpath, recursive=False):
    """Load metadata records from directory of files to database"""
    repo = repository.Repository(database, context, table=table)

    file_list = []

    if recursive:
        for root, dirs, files in os.walk(xml_dirpath):
            for mfile in files:
                if mfile.endswith('.xml'):
                    file_list.append(os.path.join(root, mfile))
    else:
        for rec in glob(os.path.join(xml_dirpath, '*.xml')):
            file_list.append(rec)

    total = len(file_list)
    counter = 0

    for recfile in file_list:
        counter += 1
        LOGGER.info('Processing file %s (%d of %d)', recfile, counter, total)
        # read document
        try:
            exml = etree.parse(recfile)
        except Exception, err:
            LOGGER.warn('XML document is not well-formed: %s', str(err))
            continue

        record = metadata.parse_record(context, exml, repo)

        for rec in record:
            LOGGER.info('Inserting %s %s into database %s, table %s ....',
                        rec.typename, rec.identifier, database, table)

            # TODO: do this as CSW Harvest
            try:
                repo.insert(rec, 'local', util.get_today_and_now())
                LOGGER.info('Inserted')
            except Exception, err:
                LOGGER.warn('ERROR: not inserted %s', err)


def export_records(context, database, table, xml_dirpath):
    """Export metadata records from database to directory of files"""
    repo = repository.Repository(database, context, table=table)

    LOGGER.info('Querying database %s, table %s ....', database, table)
    records = repo.session.query(repo.dataset)

    LOGGER.info('Found %d records\n', records.count())

    LOGGER.info('Exporting records\n')

    dirpath = os.path.abspath(xml_dirpath)

    if not os.path.exists(dirpath):
        LOGGER.info('Directory %s does not exist.  Creating...', dirpath)
        try:
            os.makedirs(dirpath)
        except OSError, err:
            raise RuntimeError('Could not create %s %s' % (dirpath, err))

    for record in records.all():
        identifier = \
            getattr(record,
                    context.md_core_model['mappings']['pycsw:Identifier'])

        LOGGER.info('Processing %s', identifier)
        if identifier.find(':') != -1:  # it's a URN
            # sanitize identifier
            LOGGER.info(' Sanitizing identifier')
            identifier = identifier.split(':')[-1]

        # write to XML document
        filename = os.path.join(dirpath, '%s.xml' % identifier)
        try:
            LOGGER.info('Writing to file %s', filename)
            with open(filename, 'w') as xml:
                xml.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                xml.write(record.xml)
        except Exception, err:
            raise RuntimeError("Error writing to %s" % filename, err)


def refresh_harvested_records(context, database, table, url):
    """refresh / harvest all non-local records in repository"""
    from owslib.csw import CatalogueServiceWeb

    # get configuration and init repo connection
    repos = repository.Repository(database, context, table=table)

    # get all harvested records
    count, records = repos.query(constraint={'where': 'source != "local"'})

    if int(count) > 0:
        LOGGER.info('Refreshing %s harvested records', count)
        csw = CatalogueServiceWeb(url)

        for rec in records:
            source = \
                getattr(rec,
                        context.md_core_model['mappings']['pycsw:Source'])
            schema = \
                getattr(rec,
                        context.md_core_model['mappings']['pycsw:Schema'])
            identifier = \
                getattr(rec,
                        context.md_core_model['mappings']['pycsw:Identifier'])

            LOGGER.info('Harvesting %s (identifier = %s) ...',
                        source, identifier)
            # TODO: find a smarter way of catching this
            if schema == 'http://www.isotc211.org/2005/gmd':
                schema = 'http://www.isotc211.org/schemas/2005/gmd/'
            try:
                csw.harvest(source, schema)
                LOGGER.info(csw.response)
            except Exception, err:
                LOGGER.warn(err)
    else:
        LOGGER.info('No harvested records')


def rebuild_db_indexes(database, table):
    """Rebuild database indexes"""
    raise NotImplementedError


def optimize_db(context, database, table):
    """Optimize database"""

    LOGGER.info('Optimizing database %s', database)
    repos = repository.Repository(database, context, table=table)
    repos.connection.execute('VACUUM ANALYZE')


def gen_sitemap(context, database, table, url, output_file):
    """generate an XML sitemap from all records in repository"""

    # get configuration and init repo connection
    repos = repository.Repository(database, context, table=table)

    # write out sitemap document
    urlset = etree.Element(util.nspath_eval('sitemap:urlset',
                                            context.namespaces),
                           nsmap=context.namespaces)

    schema_loc = util.nspath_eval('xsi:schemaLocation', context.namespaces)

    urlset.attrib[schema_loc] = \
        '%s http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd' % \
        context.namespaces['sitemap']

    # get all records
    count, records = repos.query(constraint={}, maxrecords=99999999)

    LOGGER.info('Found %s records', count)

    for rec in records:
        url = etree.SubElement(urlset,
                               util.nspath_eval('sitemap:url',
                                                context.namespaces))
        uri = '%s?service=CSW&version=2.0.2&request=GetRepositoryItem&id=%s' % \
            (url,
             getattr(rec,
                     context.md_core_model['mappings']['pycsw:Identifier']))
        etree.SubElement(url,
                         util.nspath_eval('sitemap:loc',
                                          context.namespaces)).text = uri

    # write to file
    LOGGER.info('Writing to %s', output_file)
    with open(output_file, 'w') as ofile:
        ofile.write(etree.tostring(urlset, pretty_print=1,
                    encoding='utf8', xml_declaration=1))


def gen_opensearch_description(context, mdata, url, output_file):
    """generate an OpenSearch Description document"""

    node0 = etree.Element('OpenSearchDescription',
                          nsmap={None: context.namespaces['os']})

    etree.SubElement(node0, 'ShortName').text = 'pycsw'
    etree.SubElement(node0, 'LongName').text = mdata['identification_title']
    etree.SubElement(node0, 'Description').text = \
        mdata['identification_abstract']
    etree.SubElement(node0, 'Tags').text = \
        ' '.join(mdata['identification_keywords'].split(','))

    node1 = etree.SubElement(node0, 'Url')
    node1.set('type', 'text/html')
    node1.set('method', 'get')
    node1.set('template', '%s?mode=opensearch&service=CSW&version=2.0.2&request=GetRecords&elementsetname=brief&typenames=csw:Record&resulttype=results&constraintlanguage=CQL_TEXT&constraint_language_version=1.1.0&constraint=csw:AnyText like "%%{searchTerms}%%" ' % url)

    node1 = etree.SubElement(node0, 'Image')
    node1.set('type', 'image/vnd.microsoft.icon')
    node1.set('width', '16')
    node1.set('height', '16')
    node1.text = 'http://pycsw.org/_static/favicon.ico'

    etree.SubElement(node0, 'Developer').text = mdata['contact_name']
    etree.SubElement(node0, 'Contact').text = mdata['contact_email']
    etree.SubElement(node0, 'Attribution').text = mdata['provider_name']

    # write to file
    LOGGER.info('Writing to %s', output_file)
    with open(output_file, 'w') as ofile:
        ofile.write(etree.tostring(node0, pretty_print=1,
                    encoding='UTF-8', xml_declaration=1))


def post_xml(url, xml, timeout=30):
    """Execute HTTP XML POST request and print response"""

    LOGGER.info('Executing HTTP POST request %s on server %s', xml, url)

    from owslib.util import http_post
    try:
        return http_post(url=url, request=open(xml).read(), timeout=timeout)
    except Exception, err:
        raise RuntimeError(err)


def get_sysprof():
    """Get versions of dependencies"""

    none = 'Module not found'

    try:
        import sqlalchemy
        vsqlalchemy = sqlalchemy.__version__
    except ImportError:
        vsqlalchemy = none

    try:
        import pyproj
        vpyproj = pyproj.__version__
    except ImportError:
        vpyproj = none

    try:
        import shapely
        try:
            vshapely = shapely.__version__
        except AttributeError:
            import shapely.geos
            vshapely = shapely.geos.geos_capi_version
    except ImportError:
        vshapely = none

    try:
        import owslib
        try:
            vowslib = owslib.__version__
        except AttributeError:
            vowslib = 'Module found, version not specified'
    except ImportError:
        vowslib = none

    return '''pycsw system profile
    --------------------
    Python version: %s
    os: %s
    SQLAlchemy: %s
    Shapely: %s
    lxml: %s
    pyproj: %s
    OWSLib: %s''' % (sys.version_info, sys.platform, vsqlalchemy,
                     vshapely, etree.__version__, vpyproj, vowslib)


def validate_xml(xml, xsd):
    """Validate XML document against XML Schema"""

    LOGGER.info('Validating %s against schema %s', xml, xsd)

    schema = etree.XMLSchema(file=xsd)
    parser = etree.XMLParser(schema=schema)

    try:
        valid = etree.parse(xml, parser)
        return 'Valid'
    except Exception, err:
        raise RuntimeError('ERROR: %s' % str(err))
