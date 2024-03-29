# -*- coding: utf-8 -*-

"""
    S3XML Toolkit

    @see: U{B{I{S3XRC}} <http://eden.sahanafoundation.org/wiki/S3XRC>}

    @requires: U{B{I{gluon}} <http://web2py.com>}
    @requires: U{B{I{lxml}} <http://codespeak.net/lxml>}

    @author: Dominic König <dominic[at]aidiq.com>

    @copyright: 2009-2011 (c) Sahana Software Foundation
    @license: MIT

    Permission is hereby granted, free of charge, to any person
    obtaining a copy of this software and associated documentation
    files (the "Software"), to deal in the Software without
    restriction, including without limitation the rights to use,
    copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following
    conditions:

    The above copyright notice and this permission notice shall be
    included in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
    EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
    OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
    NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
    HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
    WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
    OTHER DEALINGS IN THE SOFTWARE.
"""

__all__ = ["S3XML"]

import sys
import csv
import datetime
import urllib2

from gluon import *
from gluon.storage import Storage
import gluon.contrib.simplejson as json

from s3codec import S3Codec

from lxml import etree

# =============================================================================

class S3XML(S3Codec):
    """
        XML toolkit for S3XRC
    """

    namespace = "sahana"

    CACHE_TTL = 20 # time-to-live of RAM cache for field representations

    UID = "uuid"
    MCI = "mci"
    DELETED = "deleted"
    CTIME = "created_on"
    CUSER = "created_by"
    MTIME = "modified_on"
    MUSER = "modified_by"
    OROLE = "owned_by_role"
    OUSER = "owned_by_user"

    # GIS field names
    Lat = "lat"
    Lon = "lon"

    IGNORE_FIELDS = [
            "id",
            "deleted_fk",
            "owned_by_organisation",
            "owned_by_facility"]

    FIELDS_TO_ATTRIBUTES = [
            "id",
            "admin",
            CUSER,
            MUSER,
            OROLE,
            OUSER,
            CTIME,
            MTIME,
            UID,
            MCI,
            DELETED]

    ATTRIBUTES_TO_FIELDS = [
            "admin",
            CUSER,
            MUSER,
            OROLE,
            OUSER,
            CTIME,
            MTIME,
            MCI,
            DELETED]

    TAG = Storage(
        root="s3xml",
        resource="resource",
        reference="reference",
        meta="meta",
        data="data",
        list="list",
        item="item",
        object="object",
        select="select",
        field="field",
        option="option",
        options="options",
        fields="fields",
        table="table",
        row="row",
        col="col")

    ATTRIBUTE = Storage(
        id="id",
        name="name",
        table="table",
        field="field",
        value="value",
        resource="resource",
        ref="ref",
        domain="domain",
        url="url",
        filename="filename",
        error="error",
        start="start",
        limit="limit",
        success="success",
        results="results",
        lat="lat",
        latmin="latmin",
        latmax="latmax",
        lon="lon",
        lonmin="lonmin",
        lonmax="lonmax",
        marker="marker",
        shape="shape",  # for GIS Feature Queries
        size="size",    # for GIS Feature Queries
        colour="colour",# for GIS Feature Queries
        popup="popup",  # for GIS Feature Layers/Queries
        sym="sym",      # For GPS
        type="type",
        readable="readable",
        writable="writable",
        has_options="has_options",
        tuid="tuid",
        label="label",
        comment="comment")

    ACTION = Storage(
        create="create",
        read="read",
        update="update",
        delete="delete")

    PREFIX = Storage(
        resource="$",
        options="$o",
        reference="$k",
        attribute="@",
        text="$")

    # -------------------------------------------------------------------------
    def __init__(self, manager):
        """
            Constructor

            @param manager: the S3ResourceController
        """

        self.manager = manager

        self.domain = manager.domain
        self.error = None

        self.filter_mci = False # Set to true to suppress export at MCI<0

    # XML+XSLT tools ==========================================================
    #
    def parse(self, source):
        """
            Parse an XML source into an element tree

            @param source: the XML source -
                can be a file-like object, a filename or a HTTP/HTTPS/FTP URL
        """

        self.error = None
        if isinstance(source, basestring) and source[:5] == "https":
            try:
                source = urllib2.urlopen(source)
            except:
                pass
        try:
            parser = etree.XMLParser(no_network=False)
            result = etree.parse(source, parser)
            return result
        except:
            e = sys.exc_info()[1]
            self.error = e
            return None

    # -------------------------------------------------------------------------
    def transform(self, tree, stylesheet_path, **args):
        """
            Transform an element tree with XSLT

            @param tree: the element tree
            @param stylesheet_path: pathname of the XSLT stylesheet
            @param args: dict of arguments to pass to the stylesheet
        """

        self.error = None

        if args:
            _args = [(k, "'%s'" % args[k]) for k in args]
            _args = dict(_args)
        else:
            _args = None
        stylesheet = self.parse(stylesheet_path)

        if stylesheet:
            try:
                ac = etree.XSLTAccessControl(read_file=True, read_network=True)
                transformer = etree.XSLT(stylesheet, access_control=ac)
                if _args:
                    result = transformer(tree, **_args)
                else:
                    result = transformer(tree)
                return result
            except:
                e = sys.exc_info()[1]
                self.error = e
                return None
        else:
            # Error parsing the XSL stylesheet
            return None

    # -------------------------------------------------------------------------
    @staticmethod
    def tostring(tree, xml_declaration=True, pretty_print=False):
        """
            Convert an element tree into XML as string

            @param tree: the element tree
            @param xml_declaration: add an XML declaration to the output
            @param pretty_print: provide pretty formatted output
        """

        return etree.tostring(tree,
                              xml_declaration=xml_declaration,
                              encoding="utf-8",
                              pretty_print=True)

    # -------------------------------------------------------------------------
    def tree(self, elements,
             root=None,
             domain=None,
             url=None,
             start=None,
             limit=None,
             results=None):
        """
            Builds a S3XML tree from a list of elements

            @param elements: list of <resource> elements
            @param root: the root element to link the tree to
            @param domain: name of the current domain
            @param url: url of the request
            @param start: the start record (in server-side pagination)
            @param limit: the page size (in server-side pagination)
            @param results: number of total available results
        """

        # For now we do not nsmap, because the default namespace cannot be
        # matched in XSLT stylesheets (need explicit prefix) and thus this
        # would require a rework of all existing stylesheets (which is
        # however useful)

        success = False

        if root is None:
            root = etree.Element(self.TAG.root)
        if elements is not None or len(root):
            success = True
        root.set(self.ATTRIBUTE.success, json.dumps(success))
        if start is not None:
            root.set(self.ATTRIBUTE.start, str(start))
        if limit is not None:
            root.set(self.ATTRIBUTE.limit, str(limit))
        if results is not None:
            root.set(self.ATTRIBUTE.results, str(results))
        if elements is not None:
            root.extend(elements)
        if domain:
            root.set(self.ATTRIBUTE.domain, self.domain)
        if url:
            root.set(self.ATTRIBUTE.url, current.response.s3.base_url)
        root.set(self.ATTRIBUTE.latmin,
                 str(current.gis.get_bounds()["min_lat"]))
        root.set(self.ATTRIBUTE.latmax,
                 str(current.gis.get_bounds()["max_lat"]))
        root.set(self.ATTRIBUTE.lonmin,
                 str(current.gis.get_bounds()["min_lon"]))
        root.set(self.ATTRIBUTE.lonmax,
                 str(current.gis.get_bounds()["max_lon"]))
        return etree.ElementTree(root)

    # -------------------------------------------------------------------------
    def export_uid(self, uid):
        """
            Exports UIDs with domain prefix

            @param uid: the UID
        """

        if not uid:
            return uid
        if uid.startswith("urn:"):
            return uid
        else:
            x = uid.find("/")
            if (x < 1 or x == len(uid)-1) and self.domain:
                return "%s/%s" % (self.domain, uid)
            else:
                return uid

    # -------------------------------------------------------------------------
    def import_uid(self, uid):
        """
            Imports UIDs with domain prefixes

            @param uid: the UID
        """

        if not uid or not self.domain:
            return uid
        if uid.startswith("urn:"):
            return uid
        else:
            x = uid.find("/")
            if x < 1 or x == len(uid)-1:
                return uid
            else:
                (_domain, _uid) = uid.split("/", 1)
                if _domain == self.domain:
                    return _uid
                else:
                    return uid

    # Data export =============================================================
    #
    def represent(self, table, f, v):
        """
            Get the representation of a field value

            @param table: the database table
            @param f: the field name
            @param v: the value
        """

        if f in (self.CUSER, self.MUSER, self.OUSER):
            return self.represent_user(v)
        elif f in (self.OROLE):
            return self.represent_role(v)

        manager = self.manager
        return manager.represent(table[f],
                                 value=v,
                                 strip_markup=True,
                                 xml_escape=True)

    # -------------------------------------------------------------------------
    @staticmethod
    def represent_user(user_id):
        db = current.db
        cache = current.cache
        auth = current.auth
        utable = auth.settings.table_user
        user = None
        if "email" in utable:
            user = db(utable.id == user_id).select(
                        utable.email,
                        limitby=(0, 1),
                        cache=(cache.ram, S3XML.CACHE_TTL)).first()
        if user:
            return user.email
        return None

    # -------------------------------------------------------------------------
    @staticmethod
    def represent_role(role_id):
        db = current.db
        cache = current.cache
        auth = current.auth
        gtable = auth.settings.table_group
        role = None
        if "role" in gtable:
            role = db(gtable.id == role_id).select(
                        gtable.role,
                        limitby=(0, 1),
                        cache=(cache.ram, S3XML.CACHE_TTL)).first()
        if role:
            return role.role
        return None

    # -------------------------------------------------------------------------
    def rmap(self, table, record, fields):
        """
            Generates a reference map for a record

            @param table: the database table
            @param record: the record
            @param fields: list of reference field names in this table
        """

        db = current.db
        reference_map = []

        for f in fields:
            ids = record.get(f, None)
            if not ids:
                continue
            if not isinstance(ids, (list, tuple)):
                ids = [ids]
            multiple = False
            fieldtype = str(table[f].type)
            if fieldtype.startswith("reference"):
                ktablename = fieldtype[10:]
            elif fieldtype.startswith("list:reference"):
                ktablename = fieldtype[15:]
                multiple = True
            else:
                continue

            ktable = db[ktablename]
            pkey = ktable._id.name

            uid = None
            uids = None
            supertable = None

            if ktable._id.name != "id" and "instance_type" in ktable.fields:
                if multiple:
                    continue
                krecord = ktable[ids[0]]
                if not krecord:
                    continue
                ktablename = krecord.instance_type
                uid = krecord[self.UID]
                if ktablename == str(table) and \
                   self.UID in record and record[self.UID] == uid:
                    continue
                uids = [uid]
            elif self.UID in ktable.fields:
                query = (ktable[pkey].belongs(ids))
                if "deleted" in ktable:
                    query = (ktable.deleted == False) & query
                if self.filter_mci and "mci" in ktable:
                    query = (ktable.mci >= 0) & query
                krecords = current.db(query).select(ktable[self.UID])
                if krecords:
                    uids = [r[self.UID] for r in krecords if r[self.UID]]
                    if ktable._tablename != current.auth.settings.table_group_name:
                        uids = [self.export_uid(u) for u in uids]
                else:
                    continue
            else:
                query = (ktable._id.belongs(ids))
                if "deleted" in ktable:
                    query = (ktable.deleted == False) & query
                if self.filter_mci and "mci" in ktable:
                    query = (ktable.mci >= 0) & query
                if not current.db(query).count():
                    continue

            value = str(table[f].formatter(record[f])).decode("utf-8")
            text = self.xml_encode(value)
            if table[f].represent:
                text = self.represent(table, f, record[f])

            reference_map.append(Storage(field=f,
                                         table=ktablename,
                                         multiple=multiple,
                                         id=ids,
                                         uid=uids,
                                         text=text,
                                         value=value))
        return reference_map

    # -------------------------------------------------------------------------
    def add_references(self, element, rmap, show_ids=False):
        """
            Adds <reference> elements to a <resource>

            @param element: the <resource> element
            @param rmap: the reference map for the corresponding record
            @param show_ids: insert the record ID as attribute in references
        """

        for i in xrange(0, len(rmap)):
            r = rmap[i]
            reference = etree.SubElement(element, self.TAG.reference)
            reference.set(self.ATTRIBUTE.field, r.field)
            reference.set(self.ATTRIBUTE.resource, r.table)
            if show_ids:
                if r.multiple:
                    ids = json.dumps(r.id)
                else:
                    ids = "%s" % r.id[0]
                reference.set(self.ATTRIBUTE.id, ids)
            if r.uid:
                if r.multiple:
                    uids = json.dumps(r.uid)
                else:
                    uids = "%s" % r.uid[0]
                reference.set(self.UID, str(uids).decode("utf-8"))
                reference.text = r.text
            else:
                reference.set(self.ATTRIBUTE.value, r.value)
                # TODO: add in-line resource
            r.element = reference

    # -------------------------------------------------------------------------
    def gis_encode(self,
                   resource,
                   record,
                   rmap,
                   download_url="",
                   marker=None,
                   shape=None,          # Used by Feature Queries
                   size=None,           # Used by Feature Queries
                   colour=None,         # Used by Feature Queries
                   popup_url=None,      # Used by Feature Queries
                   popup_label=None,    # Used by Internal Feature Layers & Feature Queries
                   popup_fields=None):  # Used by Internal Feature Layers
        """
            GIS-encodes location references

            @param resource: the referencing resource
            @param record: the particular record
            @param rmap: list of references to encode
            @param download_url: download URL of this instance
            @param marker: filename to override filenames in marker URLs
            @param shape: shape as alternative to marker
            @param size: size of shape
            @param colour: colour of shape
            @param popup_url:  URL used for onClick Popup contents
            @param popup_label:  used to build HTML in the onHover Tooltip
            @param popup_fields: used to build HTML in the onHover Tooltip
        """

        if not current.gis:
            return

        gis = current.gis
        db = current.db

        # Quicker to download Icons from Static
        # also doesn't require authentication so KML files can work in
        # Google Earth
        download_url = download_url.replace("default/download",
                                            "static/img/markers")

        references = filter(lambda r:
                            r.element is not None and \
                            self.Lat in db[r.table].fields and \
                            self.Lon in db[r.table].fields,
                            rmap)

        for i in xrange(0, len(references)):
            r = references[i]
            if len(r.id) == 1:
                r_id = r.id[0]
            else:
                continue # Multi-reference
            ktable = db[r.table]
            LatLon = db(ktable.id == r_id).select(ktable[self.Lat],
                                                  ktable[self.Lon],
                                                  limitby=(0, 1))
            if LatLon:
                LatLon = LatLon.first()
                if LatLon[self.Lat] is not None and \
                   LatLon[self.Lon] is not None:
                    r.element.set(self.ATTRIBUTE.lat,
                                  "%.6f" % LatLon[self.Lat])
                    r.element.set(self.ATTRIBUTE.lon,
                                  "%.6f" % LatLon[self.Lon])
                    if shape or size or colour:
                        # Feature Queries
                        # We don't want a default Marker if these are specified
                        if shape:
                            r.element.set(self.ATTRIBUTE.shape, shape)
                        if size:
                            r.element.set(self.ATTRIBUTE.size, size)
                        if colour:
                            r.element.set(self.ATTRIBUTE.colour, colour)

                    # Lookup Marker (Icon)
                    # @ToDo: Remove the Public URL to keep filesize small when
                    # loading off same server? (GeoJSON &layer=xx)
                    # @ToDo: Return the markers outside the records
                    #        (as there are many less of them)
                    #        & use the stylesheet to hook-up appropriately
                    elif marker:
                        marker_url = "%s/gis_marker.image.%s.png" % \
                                     (download_url, marker)
                    else:
                        marker = gis.get_marker(tablename=resource.tablename, record=record)
                        marker_url = "%s/%s" % (download_url, marker.image)
                    r.element.set(self.ATTRIBUTE.marker, marker_url)
                    # Lookup GPS Marker (Symbol)
                    symbol = gis.get_gps_marker(resource.tablename, record)
                    r.element.set(self.ATTRIBUTE.sym, symbol)
                    if popup_fields:
                        # Internal feature Layers
                        # Build the HTML for the onHover Tooltip
                        T = current.T
                        popup_fields = popup_fields.split("/")
                        fieldname = popup_fields[0]
                        if popup_label:
                            tooltip = "(%s)" % T(popup_label)
                        else:
                            tooltip = ""
                        try:
                            value = record[fieldname]
                            if value:
                                field = resource.table[fieldname]
                                # @ToDo: Slow query which would be
                                # good to optimise
                                represent = gis.get_representation(field,
                                                                   value)
                                tooltip = "%s %s" % (represent, tooltip)
                        except:
                            # This field isn't in the table
                            pass

                        for fieldname in popup_fields:
                            try:
                                if fieldname != popup_fields[0]:
                                    value = record[fieldname]
                                    if value:
                                        field = resource.table[fieldname]
                                        # @ToDo: Slow query which would be
                                        # good to optimise
                                        represent = gis.get_representation(
                                                        field, value)
                                        tooltip = "%s<br />%s" % (tooltip,
                                                                  represent)
                            except:
                                # This field isn't in the table
                                pass
                        try:
                            # encode suitable for use as XML attribute
                            tooltip = self.xml_encode(tooltip).decode("utf-8")
                        except:
                            pass
                        else:
                            r.element.set(self.ATTRIBUTE.popup, tooltip)

                        # Build the URL for the onClick Popup contents
                        if not popup_url:
                            url = URL(resource.prefix,
                                      resource.name).split(".", 1)[0]
                            popup_url = "%s/%i.plain" % (url,
                                                         record.id)
                    elif popup_label:
                        # Feature Queries
                        # This is the pre-generated HTML for the onHover Tooltip
                        r.element.set(self.ATTRIBUTE.popup, popup_label)

                    if popup_url:
                        # @ToDo: add the Public URL so that layers can
                        # be loaded off remote Sahana instances
                        # (make this optional to keep filesize small
                        # when not needed?)
                        r.element.set(self.ATTRIBUTE.url, popup_url)

    # -------------------------------------------------------------------------
    def resource(self, parent, table, record,
                 fields=[],
                 postprocess=None,
                 url=None):
        """
            Creates a <resource> element from a record

            @param parent: the parent element in the document tree
            @param table: the database table
            @param record: the record
            @param fields: list of field names to include
            @param postprocess: post-process hook (function to process
                <resource> elements after compilation)
            @param url: URL of the record
        """

        deleted = False
        download_url = current.response.s3.download_url or ""

        ATTRIBUTE = self.ATTRIBUTE

        if parent is not None:
            elem = etree.SubElement(parent, self.TAG.resource)
        else:
            elem = etree.Element(self.TAG.resource)
        elem.set(ATTRIBUTE.name, table._tablename)

        # UID
        if self.UID in table.fields and self.UID in record:
            uid = record[self.UID]
            uid = str(table[self.UID].formatter(uid)).decode("utf-8")
            if table._tablename != current.auth.settings.table_group_name:
                elem.set(self.UID, self.export_uid(uid))
            else:
                elem.set(self.UID, uid)

        # DELETED
        if self.DELETED in record and record[self.DELETED]:
            deleted = True
            elem.set(self.DELETED, "True")
            # export only MTIME with deleted records
            fields = [self.MTIME]

        # GIS marker
        if table._tablename == "gis_location" and current.gis:
            marker = current.gis.get_marker() # Default Marker
            # Quicker to download Icons from Static
            # also doesn't require authentication so KML files can work in
            # Google Earth
            marker_download_url = download_url.replace("default/download",
                                                       "static/img/markers")
            marker_url = "%s/%s" % (marker_download_url, marker.image)
            elem.set(ATTRIBUTE.marker, marker_url)
            symbol = "White Dot"
            elem.set(ATTRIBUTE.sym, symbol)

        # Fields
        for f in fields:
            v = record.get(f, None)
            if f == self.MCI and v is None:
                v = 0
            if f == self.DELETED:
                continue
            if f not in table.fields or v is None:
                continue

            fieldtype = str(table[f].type)
            if fieldtype == "datetime":
                value = self.encode_iso_datetime(v).decode("utf-8")
                text = self.xml_encode(value)
            elif fieldtype in ("date", "time"):
                value = str(table[f].formatter(v)).decode("utf-8")
                text = self.xml_encode(value)
            else:
                value = json.dumps(v).decode("utf-8")
                text = self.xml_encode(
                            str(table[f].formatter(v)).decode("utf-8"))
            if table[f].represent:
                text = self.represent(table, f, v)

            if f in self.FIELDS_TO_ATTRIBUTES:
                if f == self.MCI:
                    elem.set(self.MCI, str(int(v) + 1))
                else:
                    elem.set(f, text)
            elif fieldtype == "upload":
                fileurl = "%s/%s" % (download_url, v)
                filename = v
                if filename:
                    data = etree.SubElement(elem, self.TAG.data)
                    data.set(ATTRIBUTE.field, f)
                    data.set(ATTRIBUTE.url, fileurl)
                    data.set(ATTRIBUTE.filename, filename)
            elif fieldtype == "password":
                # Do not export password fields
                data = etree.SubElement(elem, self.TAG.data)
                data.set(ATTRIBUTE.field, f)
                data.text = value
                #continue
            elif fieldtype == "blob":
                # Not implemented
                continue
            else:
                data = etree.SubElement(elem, self.TAG.data)
                data.set(ATTRIBUTE.field, f)
                if table[f].represent or \
                   fieldtype not in ("string", "text"):
                    data.set(ATTRIBUTE.value, value)
                data.text = text

        if url and not deleted:
            elem.set(ATTRIBUTE.url, url)

        postp = None
        if postprocess is not None:
            try:
                postp = postprocess.get(str(table), None)
            except:
                postp = postprocess
        if postp and callable(postp):
            elem = postp(table, elem)

        return elem

    # Data import =============================================================
    #
    @classmethod
    def select_resources(cls, tree, tablename):
        """
            Selects resources from an element tree

            @param tree: the element tree
            @param tablename: table name to search for
        """

        resources = []

        if isinstance(tree, etree._ElementTree):
            root = tree.getroot()
            if root is None or root.tag != cls.TAG.root:
                return resources
        else:
            root = tree

        if root is None or not len(root):
            return resources
        expr = './%s[@%s="%s"]' % \
               (cls.TAG.resource, cls.ATTRIBUTE.name, tablename)
        resources = root.xpath(expr)
        return resources

    # -------------------------------------------------------------------------
    @staticmethod
    def _dtparse(dtstr, field_type="datetime"):
        """
            Helper function to parse a string into a date,
            time or datetime value (always returns UTC datetimes).

            @param dtstr: the string
            @param field_type: the field type
        """

        error = None
        value = None

        try:
            dt = S3Codec.decode_iso_datetime(str(dtstr))
            value = S3Codec.as_utc(dt)
        except:
            error = sys.exc_info()[1]
        if error is None:
            if field_type == "date":
                value = value.date()
            elif field_type == "time":
                value = value.time()
        return (value, error)

    # -------------------------------------------------------------------------
    def record(self, table, element,
               original=None,
               files=[],
               preprocess=None,
               validate=None,
               skip=[]):
        """
            Creates a record (Storage) from a <resource> element and validates
            it

            @param table: the database table
            @param element: the element
            @param original: the original record
            @param files: list of attached upload files
            @param preprocess: pre-process hook (function to process elements
                before they get parsed and validated)
            @param validate: validate hook (function to validate fields)
            @param skip: fields to skip
        """

        valid = True
        record = Storage()

        db = current.db
        auth = current.auth
        utable = auth.settings.table_user
        gtable = auth.settings.table_group

        # Preprocess the element
        prepare = None
        if preprocess is not None:
            try:
                prepare = preprocess.get(str(table), None)
            except:
                prepare = preprocess
        if prepare and callable(prepare):
            element = prepare(table, element)

        # Extract the UUID
        if self.UID in table.fields and self.UID not in skip:
            uid = self.import_uid(element.get(self.UID, None))
            if uid:
                record[self.UID] = uid

        # Attributes
        deleted = False
        for f in self.ATTRIBUTES_TO_FIELDS:
            if f == self.DELETED:
                v = element.get(f, None)
                if v == "True":
                    record[f] = deleted = True
                    break
                else:
                    continue
            if f in self.IGNORE_FIELDS or f in skip:
                continue
            elif f in (self.CUSER, self.MUSER, self.OUSER):
                v = element.get(f, None)
                if v and utable and "email" in utable:
                    query = utable.email == v
                    user = db(query).select(utable.id, limitby=(0, 1)).first()
                    if user:
                        record[f] = user.id
                continue
            elif f == self.OROLE:
                v = element.get(f, None)
                if v and gtable and "role" in gtable:
                    query = gtable.role == v
                    role = db(query).select(gtable.id, limitby=(0, 1)).first()
                    if role:
                        record[f] = role.id
                continue
            if f in table.fields:
                v = value = element.get(f, None)
                if value is not None:
                    field_type = str(table[f].type)
                    if field_type in ("datetime", "date", "time"):
                        (value, error) = self._dtparse(v,
                                                       field_type=field_type)
                    elif validate is not None:
                        try:
                            (value, error) = validate(table, original, f, v)
                        except AttributeError:
                            # No such field
                            continue
                    if error:
                        element.set(self.ATTRIBUTE.error,
                                    "%s: %s" % (f, error))
                        valid = False
                        continue
                    record[f]=value

        if deleted:
            return record

        # Fields
        for child in element.findall("data"):
            f = child.get(self.ATTRIBUTE.field, None)
            if not f or f not in table.fields:
                continue
            if f in self.IGNORE_FIELDS or f in skip:
                continue
            field_type = str(table[f].type)
            if field_type in ("id", "blob"):
                continue
            elif field_type == "upload":
                download_url = child.get(self.ATTRIBUTE.url, None)
                filename = child.get(self.ATTRIBUTE.filename, None)
                upload = None
                if filename and filename in files:
                    upload = files[filename]
                elif download_url:
                    import urllib2
                    try:
                        upload = urllib2.urlopen(download_url)
                    except IOError:
                        continue
                if upload:
                    field = table[f]
                    value = field.store(upload, filename)
                else:
                    continue
            else:
                value = child.get(self.ATTRIBUTE.value, None)

            error = None
            skip_validation = False

            if value is None:
                if field_type == "password":
                    value = child.text
                    # Do not encrypt the password if it already
                    # comes encrypted:
                    skip_validation = True
                else:
                    value = self.xml_decode(child.text)

            if value is None and field_type in ("string", "text"):
                value = ""
            elif value == "" and not field_type in ("string", "text"):
                value = None

            if value is not None:
                if field_type in ("datetime", "date", "time"):
                    (value, error) = self._dtparse(value,
                                                   field_type=field_type)
                    skip_validation = True
                elif isinstance(value, basestring) and len(value):
                    try:
                        value = json.loads(value)
                    except:
                        pass

                if validate is not None and not skip_validation:
                    if not isinstance(value, (basestring, list, tuple)):
                        v = str(value)
                    elif isinstance(value, basestring):
                        v = value.encode("utf-8")
                    else:
                        v = value
                    try:
                        if field_type == "upload":
                            fn, ff = field.retrieve(value)
                            v = Storage({"filename":fn, "file": ff})
                            (v, error) = validate(table, original, f, v)
                        elif field_type == "password":
                            v = value
                            (value, error) = validate(table, None, f, v)
                        else:
                            (value, error) = validate(table, original, f, v)
                    except AttributeError:
                        # No such field
                        continue
                    except:
                        error = sys.exc_info()[1]

                child.set(self.ATTRIBUTE.value, str(v).decode("utf-8"))
                if error:
                    child.set(self.ATTRIBUTE.error, "%s: %s" % (f, error))
                    valid = False
                    continue

                record[f] = value

        if valid:
            return record
        else:
            return None

    # Data model helpers ======================================================
    #
    @classmethod
    def get_field_options(cls, table, fieldname, parent=None, show_uids=False):
        """
            Get options of a field as <select>

            @param table: the table
            @param fieldname: the fieldname
            @param parent: the parent element in the tree
        """

        options = []
        if fieldname in table.fields:
            field = table[fieldname]
            requires = field.requires
            if not isinstance(requires, (list, tuple)):
                requires = [requires]
            if requires:
                r = requires[0]
                if isinstance(r, IS_EMPTY_OR):
                    r = r.other
                try:
                    options = r.options()
                except:
                    pass

        if options:
            if parent is not None:
                select = etree.SubElement(parent, cls.TAG.select)
            else:
                select = etree.Element(cls.TAG.select)
            select.set(cls.ATTRIBUTE.name, fieldname)
            select.set(cls.ATTRIBUTE.id,
                       "%s_%s" % (table._tablename, fieldname))

            uids = Storage()
            if show_uids:
                ftype = str(field.type)
                if ftype[:9] == "reference":
                    ktablename = ftype[10:]
                    current.manager.load(ktablename)
                    try:
                        ktable = current.db[ktablename]
                    except:
                        pass
                    else:
                        ids = [o[0] for o in options]
                        if ids and cls.UID in ktable.fields:
                            query = ktable._id.belongs(ids)
                            rows = current.db(query).select(ktable._id, ktable[cls.UID])
                            uids = Storage((str(r[ktable._id.name]), r[cls.UID])
                                        for r in rows)

            for (value, text) in options:
                if show_uids and str(value) in uids:
                    uid = uids[str(value)]
                else:
                    uid = None
                value = cls.xml_encode(str(value).decode("utf-8"))
                try:
                    markup = etree.XML(str(text))
                    text = markup.xpath(".//text()")
                    if text:
                        text = " ".join(text)
                    else:
                        text = ""
                except:
                    pass
                text = cls.xml_encode(str(text).decode("utf-8"))
                option = etree.SubElement(select, cls.TAG.option)
                option.set(cls.ATTRIBUTE.value, value)
                if uid:
                    option.set(cls.UID, uid)
                option.text = text
        elif parent is not None:
            return None
        else:
            return etree.Element(cls.TAG.select)

        return select

    # -------------------------------------------------------------------------
    def get_options(self, prefix, name, fields=None, show_uids=False):
        """
            Get options of option fields in a table as <select>s

            @param prefix: the application prefix
            @param name: the resource name (without prefix)
            @param fields: optional list of fieldnames
        """

        db = current.db
        tablename = "%s_%s" % (prefix, name)
        table = db.get(tablename, None)

        options = etree.Element(self.TAG.options)

        if fields:
            if not isinstance(fields, (list, tuple)):
                fields = [fields]
            if len(fields) == 1:
                return(self.get_field_options(table, fields[0],
                                              show_uids=show_uids))

        if table:
            options.set(self.ATTRIBUTE.resource, tablename)
            for f in table.fields:
                if fields and f not in fields:
                    continue
                select = self.get_field_options(table, f,
                                                parent=options,
                                                show_uids=show_uids)

        return options

    # -------------------------------------------------------------------------
    def get_fields(self, prefix, name,
                   parent=None,
                   meta=False,
                   options=False,
                   references=False,
                   labels=False):
        """
            Get fields in a table as <fields> element

            @param prefix: the application prefix
            @param name: the resource name (without prefix)
            @param parent: the parent element to append the tree to
            @param options: include option lists in option fields
            @param references: include option lists even in reference fields
        """

        db = current.db
        tablename = "%s_%s" % (prefix, name)
        table = db.get(tablename, None)

        if parent is not None:
            fields = parent
        else:
            fields = etree.Element(self.TAG.fields)
        if table:
            if parent is None:
                fields.set(self.ATTRIBUTE.resource, tablename)
            for f in table.fields:
                ftype = str(table[f].type)
                # Skip super entity references without ID
                if ftype[:9] == "reference" and \
                   not "id" in current.db[ftype[10:]].fields:
                    continue
                if f in self.IGNORE_FIELDS or ftype == "id":
                    continue
                if f in self.FIELDS_TO_ATTRIBUTES:
                    if not meta:
                        continue
                    tag = self.TAG.meta
                else:
                    tag = self.TAG.field
                readable = table[f].readable
                writable = table[f].writable
                field = etree.SubElement(fields, tag)
                if options:
                    p = field
                    if not references and \
                       ftype[:9] in ("reference", "list:refe"):
                        p = None
                else:
                    p = None
                opts = self.get_field_options(table, f, parent=p)
                field.set(self.ATTRIBUTE.name, f)
                field.set(self.ATTRIBUTE.type, ftype)
                field.set(self.ATTRIBUTE.readable, str(readable))
                field.set(self.ATTRIBUTE.writable, str(writable))
                has_options = str(opts is not None and
                                  len(opts) and True or False)
                field.set(self.ATTRIBUTE.has_options, has_options)
                if labels:
                    label = str(table[f].label).decode("utf-8")
                    field.set(self.ATTRIBUTE.label, label)
                    comment = table[f].comment
                    if comment:
                        comment = str(comment).decode("utf-8")
                    if comment and "<" in comment:
                        try:
                            markup = etree.XML(comment)
                            comment = markup.xpath(".//text()")
                            if comment:
                                comment = " ".join(comment)
                            else:
                                comment = ""
                        except etree.XMLSyntaxError:
                            comment = comment.replace(
                                        "<", "<!-- <").replace(">", "> -->")
                    if comment:
                        field.set(self.ATTRIBUTE.comment, comment)
        return fields

    # -------------------------------------------------------------------------
    def get_struct(self, prefix, name,
                   parent=None,
                   meta=False,
                   options=True,
                   references=False):
        """
            Get the table structure as XML tree

            @param prefix: the application prefix
            @param name: the tablename (without prefix)
            @param parent: the parent element to append the tree to
            @param options: include option lists in option fields
            @param references: include option lists even in reference fields

            @raise AttributeError: in case the table doesn't exist
        """

        db = current.db
        tablename = "%s_%s" % (prefix, name)
        table = db.get(tablename, None)

        if table is not None:
            if parent is not None:
                e = etree.SubElement(parent, self.TAG.resource)
            else:
                e = etree.Element(self.TAG.resource)
            e.set(self.ATTRIBUTE.name, tablename)
            self.get_fields(prefix, name,
                            parent=e,
                            meta=meta,
                            options=options,
                            references=references,
                            labels=True)
            return e
        else:
            raise AttributeError("No table like %s" % tablename)

    # JSON toolkit ============================================================
    #
    @classmethod
    def __json2element(cls, key, value, native=False):
        """
            Converts a data field from JSON into an element

            @param key: key (field name)
            @param value: value for the field
            @param native: use native mode
            @type native: bool
        """

        if isinstance(value, dict):
            return cls.__obj2element(key, value, native=native)

        elif isinstance(value, (list, tuple)):
            if not key == cls.TAG.item:
                _list = etree.Element(key)
            else:
                _list = etree.Element(cls.TAG.list)
            for obj in value:
                item = cls.__json2element(cls.TAG.item, obj,
                                           native=native)
                _list.append(item)
            return _list

        else:
            if native:
                element = etree.Element(cls.TAG.data)
                element.set(cls.ATTRIBUTE.field, key)
            else:
                element = etree.Element(key)
            if not isinstance(value, (str, unicode)):
                value = str(value)
            element.text = cls.xml_encode(value)
            return element

    # -------------------------------------------------------------------------
    @classmethod
    def __obj2element(cls, tag, obj, native=False):
        """
            Converts a JSON object into an element

            @param tag: tag name for the element
            @param obj: the JSON object
            @param native: use native mode for attributes
        """

        prefix = name = resource = field = None

        if not tag:
            tag = cls.TAG.object

        elif native:
            if tag.startswith(cls.PREFIX.reference):
                field = tag[len(cls.PREFIX.reference) + 1:]
                tag = cls.TAG.reference
            elif tag.startswith(cls.PREFIX.options):
                resource = tag[len(cls.PREFIX.options) + 1:]
                tag = cls.TAG.options
            elif tag.startswith(cls.PREFIX.resource):
                resource = tag[len(cls.PREFIX.resource) + 1:]
                tag = cls.TAG.resource
            elif not tag == cls.TAG.root:
                field = tag
                tag = cls.TAG.data

        element = etree.Element(tag)

        if native:
            if resource:
                if tag == cls.TAG.resource:
                    element.set(cls.ATTRIBUTE.name, resource)
                else:
                    element.set(cls.ATTRIBUTE.resource, resource)
            if field:
                element.set(cls.ATTRIBUTE.field, field)

        for k in obj:
            m = obj[k]
            if isinstance(m, dict):
                child = cls.__obj2element(k, m, native=native)
                element.append(child)
            elif isinstance(m, (list, tuple)):
                #l = etree.SubElement(element, k)
                for _obj in m:
                    child = cls.__json2element(k, _obj, native=native)
                    element.append(child)
            else:
                if k == cls.PREFIX.text:
                    element.text = cls.xml_encode(m)
                elif k.startswith(cls.PREFIX.attribute):
                    a = k[len(cls.PREFIX.attribute):]
                    element.set(a, cls.xml_encode(m))
                else:
                    child = cls.__json2element(k, m, native=native)
                    element.append(child)

        return element

    # -------------------------------------------------------------------------
    @classmethod
    def json2tree(cls, source, format=None):
        """
            Converts JSON into an element tree

            @param source: the JSON source
            @param format: name of the XML root element
        """

        try:
            root_dict = json.load(source)
        except (ValueError, ):
            e = sys.exc_info()[1]
            raise HTTP(400, body=cls.json_message(False, 400, e))

        native=False

        if not format:
            format=cls.TAG.root
            native=True

        if root_dict and isinstance(root_dict, dict):
            root = cls.__obj2element(format, root_dict, native=native)
            if root:
                return etree.ElementTree(root)

        return None

    # -------------------------------------------------------------------------
    @classmethod
    def __element2json(cls, element, native=False):
        """
            Converts an element into JSON

            @param element: the element
            @param native: use native mode for attributes
        """

        TAG = cls.TAG
        ATTRIBUTE = cls.ATTRIBUTE
        PREFIX = cls.PREFIX

        if element.tag == TAG.list:
            obj = []
            for child in element:
                tag = child.tag
                if not isinstance(tag, basestring):
                    continue # skip comment nodes
                if tag[0] == "{":
                    tag = tag.rsplit("}", 1)[1]
                child_obj = cls.__element2json(child, native=native)
                if child_obj:
                    obj.append(child_obj)
            return obj
        else:
            obj = {}
            for child in element:
                tag = child.tag
                if not isinstance(tag, basestring):
                    continue # skip comment nodes
                if tag[0] == "{":
                    tag = tag.rsplit("}", 1)[1]
                collapse = True
                if native:
                    if tag == TAG.resource:
                        resource = child.get(ATTRIBUTE.name)
                        tag = "%s_%s" % (PREFIX.resource, resource)
                        collapse = False
                    elif tag == TAG.options:
                        resource = child.get(ATTRIBUTE.resource)
                        tag = "%s_%s" % (PREFIX.options, resource)
                    elif tag == TAG.reference:
                        tag = "%s_%s" % (PREFIX.reference,
                                         child.get(ATTRIBUTE.field))
                    elif tag == TAG.data:
                        tag = child.get(ATTRIBUTE.field)
                child_obj = cls.__element2json(child, native=native)
                if child_obj:
                    if not tag in obj:
                        if isinstance(child_obj, list) or not collapse:
                            obj[tag] = [child_obj]
                        else:
                            obj[tag] = child_obj
                    else:
                        if not isinstance(obj[tag], list):
                            obj[tag] = [obj[tag]]
                        obj[tag].append(child_obj)

            attributes = element.attrib
            for a in attributes:
                if native:
                    if a == ATTRIBUTE.name and \
                       element.tag == TAG.resource:
                        continue
                    if a == ATTRIBUTE.resource and \
                       element.tag == TAG.options:
                        continue
                    if a == ATTRIBUTE.field and \
                       element.tag in (TAG.data, TAG.reference):
                        continue
                obj[PREFIX.attribute + a] = element.get(a)

            if element.text:
                obj[PREFIX.text] = cls.xml_decode(element.text)

            if len(obj) == 1 and obj.keys()[0] in \
               (PREFIX.text, TAG.item, TAG.list):
                obj = obj[obj.keys()[0]]

            return obj

    # -------------------------------------------------------------------------
    @classmethod
    def tree2json(cls, tree, pretty_print=False):
        """
            Converts an element tree into JSON

            @param tree: the element tree
            @param pretty_print: provide pretty formatted output
        """

        if isinstance(tree, etree._ElementTree):
            root = tree.getroot()
        else:
            root = tree

        if root.tag == cls.TAG.root:
            native = True
        else:
            native = False

        root_dict = cls.__element2json(root, native=native)

        if pretty_print:
            js = json.dumps(root_dict, indent=4)
            return "\n".join([l.rstrip() for l in js.splitlines()])
        else:
            return json.dumps(root_dict)

    # -------------------------------------------------------------------------
    @classmethod
    def csv2tree(cls, source,
                 resourcename=None,
                 delimiter=",",
                 quotechar='"'):
        """
            Convert a table-form CSV source into an element tree, consisting of
            <table name="format">, <row> and <col field="fieldname"> elements.

            @param source: the source (file-like object)
            @param resourcename: the resource name
            @param delimiter: delimiter for values
            @param quotechar: quotation character

            @todo: add a character encoding parameter to skip the guessing
        """

        root = etree.Element(cls.TAG.table)
        if resourcename is not None:
            root.set(cls.ATTRIBUTE.name, resourcename)
        def utf_8_encode(source):
            """
                UTF-8-recode the source line by line, guessing the character
                encoding of the source.
            """
            # Make this a list of all encodings you need to support (as long as
            # they are supported by Python codecs), always starting with the most
            # likely.
            encodings = ["utf-8", "iso-8859-1"]
            e = encodings[0]
            for line in source:
                if e:
                    try:
                        yield unicode(line, e, "strict").encode("utf-8")
                    except:
                        pass
                    else:
                        continue
                for encoding in encodings:
                    try:
                        yield unicode(line, encoding, "strict").encode("utf-8")
                    except:
                        continue
                    else:
                        e = encoding
                        break
        try:
            reader = csv.DictReader(utf_8_encode(source),
                                    delimiter=delimiter,
                                    quotechar=quotechar)
            for r in reader:
                row = etree.SubElement(root, cls.TAG.row)
                for k in r:
                    col = etree.SubElement(row, cls.TAG.col)
                    col.set(cls.ATTRIBUTE.field, str(k))
                    text = str(r[k])
                    if text.lower() not in ("null", "<null>"):
                        text = cls.xml_encode(unicode(text.decode("utf-8")))
                        col.text = text
        except csv.Error:
            e = sys.exc_info()[1]
            raise HTTP(400, body=cls.json_message(False, 400, e))
        return  etree.ElementTree(root)

# End =========================================================================
