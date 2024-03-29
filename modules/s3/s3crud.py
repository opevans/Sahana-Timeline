# -*- coding: utf-8 -*-

"""
    S3 RESTful CRUD Methods

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

__all__ = ["S3CRUD"]

import datetime
import os
import sys
import csv
import cgi

from gluon.storage import Storage
from gluon.dal import Row, Set
from gluon import *
from gluon.serializers import json
from gluon.tools import callback

from s3method import S3Method
from s3export import S3Exporter
from s3gis import S3MAP
from s3pdf import S3PDF
from s3tools import SQLTABLES3
from s3utils import s3_mark_required

from lxml import etree
# *****************************************************************************

class S3CRUD(S3Method):
    """
        Interactive CRUD Method Handler

    """

    # -------------------------------------------------------------------------
    def apply_method(self, r, **attr):
        """
            Apply CRUD methods

            @param r: the S3Request
            @param attr: dictionary of parameters for the method handler

            @returns: output object to send to the view
        """

        self.settings = self.manager.s3.crud

        # Pre-populate create-form?
        self.data = None
        if r.http == "GET" and not self.record:
            populate = attr.pop("populate", None)
            if callable(populate):
                try:
                    self.data = populate(r, **attr)
                except TypeError:
                    self.data = None
                except:
                    raise
            elif isinstance(populate, dict):
                self.data = populate

        if r.http == "DELETE" or self.method == "delete":
            output = self.delete(r, **attr)
        elif self.method == "create":
            output = self.create(r, **attr)
        elif self.method == "read":
            output = self.read(r, **attr)
        elif self.method == "update":
            output = self.update(r, **attr)
        elif self.method == "list":
            output = self.select(r, **attr)
        elif self.method == "upload":
            output = self.upload(r, **attr)
        else:
            r.error(501, self.manager.ERROR.BAD_METHOD)

        return output

    # -------------------------------------------------------------------------
    def create(self, r, **attr):
        """
            Create new records

            @param r: the S3Request
            @param attr: dictionary of parameters for the method handler
        """

        T = current.T

        session = current.session
        request = self.request
        response = current.response

        resource = self.resource
        table = resource.table
        tablename = resource.tablename

        representation = r.representation

        output = dict()

        # Get table configuration
        insertable = self._config("insertable", True)
        if not insertable:
            if r.method is not None:
                r.error(400, self.resource.ERROR.BAD_METHOD)
            else:
                return dict(form=None)

        authorised = self._permitted(method="create")
        if not authorised:
            if r.method is not None:
                r.unauthorised()
            else:
                return dict(form=None)

        # Get callbacks
        onvalidation = self._config("create_onvalidation") or \
                       self._config("onvalidation")
        onaccept = self._config("create_onaccept") or \
                   self._config("onaccept")

        if r.interactive:

            # Configure the HTML Form

            # Set view
            if representation in ("popup", "iframe"):
                response.view = self._view(r, "popup.html")
                output.update(caller=request.vars.caller)
            else:
                response.view = self._view(r, "create.html")

            # Title and subtitle
            if r.component:
                title = self.crud_string(r.tablename, "title_display")
                subtitle = self.crud_string(tablename, "subtitle_create")
                output.update(title=title, subtitle=subtitle)
            else:
                title = self.crud_string(tablename, "title_create")
                output.update(title=title)

            # Component join
            link = None
            if r.component:
                if resource.link is None:
                    pkey = resource.pkey
                    fkey = resource.fkey
                    table[fkey].comment = None
                    table[fkey].default = r.record[pkey]
                    table[fkey].update = r.record[pkey]
                    if r.http=="POST":
                        r.post_vars.update({fkey: r.record[pkey]})
                    table[fkey].readable = False
                    table[fkey].writable = False
                else:
                    link = Storage(resource = resource.link,
                                   master = r.record)

            # Copy record
            from_table = None
            from_record = r.get_vars.get("from_record", None)
            map_fields = r.get_vars.get("from_fields", None)

            if from_record:
                del r.get_vars["from_record"] # forget it
                if from_record.find(".") != -1:
                    from_table, from_record = from_record.split(".", 1)
                    from_table = current.db.get(from_table, None)
                    if not from_table:
                        r.error(404, self.resource.ERROR.BAD_RESOURCE)
                else:
                    from_table = table
                try:
                    from_record = long(from_record)
                except:
                    r.error(404, self.resource.ERROR.BAD_RECORD)
                authorised = self.permit("read",
                                         from_table._tablename,
                                         from_record)
                if not authorised:
                    r.unauthorised()
                if map_fields:
                    del r.get_vars["from_fields"]
                    if map_fields.find("$") != -1:
                        mf = map_fields.split(",")
                        mf = [f.find("$") != -1 and f.split("$") or \
                             [f, f] for f in mf]
                        map_fields = Storage(mf)
                    else:
                        map_fields = map_fields.split(",")

            # Success message
            message = self.crud_string(self.tablename, "msg_record_created")

            # Copy formkey if un-deleting a duplicate
            if "id" in request.post_vars:
                original = str(request.post_vars.id)
                formkey = session.get("_formkey[%s/None]" % tablename)
                formname = "%s/%s" % (tablename, original)
                session["_formkey[%s]" % formname] = formkey
                if "deleted" in table:
                    table.deleted.writable = True
                    request.post_vars.update(deleted=False)
                request.post_vars.update(_formname=formname, id=original)
                request.vars.update(**request.post_vars)
            else:
                original = None

            # Get the form
            form = self.sqlform(record_id=original,
                                from_table=from_table,
                                from_record=from_record,
                                map_fields=map_fields,
                                onvalidation=onvalidation,
                                onaccept=onaccept,
                                link=link,
                                message=message,
                                format=representation)

            # Insert subheadings
            subheadings = self._config("subheadings")
            if subheadings:
                self.insert_subheadings(form, tablename, subheadings)

            # Cancel button?
            if response.s3.cancel:
                form[0][-1][0].append(A(T("Cancel"),
                                      _href=response.s3.cancel,
                                      _class="action-lnk"))

            # Navigate-away confirmation
            if self.settings.navigate_away_confirm:
                form.append(SCRIPT("S3EnableNavigateAwayConfirm();"))

            # Put the form into output
            output.update(form=form)

            # Buttons
            buttons = self.insert_buttons(r, "list")
            if buttons:
                output.update(buttons)

            # Redirection
            create_next = self._config("create_next")
            if session.s3.rapid_data_entry and not r.component:
                create_next = r.url()

            if representation in ("popup", "iframe"):
                self.next = None
            elif not create_next:
                self.next = r.url(method="")
            else:
                try:
                    self.next = create_next(self)
                except TypeError:
                    self.next = create_next

        elif representation == "url":
            results = self.import_url(r)
            return results

        elif representation == "csv":
            csv.field_size_limit(1000000000)
            infile = request.vars.filename
            if isinstance(infile, cgi.FieldStorage) and infile.filename:
                infile = infile.file
            else:
                try:
                    infile = open(infile, "rb")
                except:
                    session.error = T("Cannot read from file: %s" % infile)
                    redirect(r.url(method="", representation="html"))
            try:
                self.import_csv(infile, table=table)
            except:
                session.error = T("Unable to parse CSV file or file contains invalid data")
            else:
                session.flash = T("Data uploaded")

        elif representation == "pdf":
            exporter = S3PDF()
            return exporter(r, **attr)

        else:
            r.error(501, self.manager.ERROR.BAD_FORMAT)

        return output

    # -------------------------------------------------------------------------
    def read(self, r, **attr):
        """
            Read a single record

            @param r: the S3Request
            @param attr: dictionary of parameters for the method handler
        """

        session = current.session
        request = self.request
        response = current.response

        resource = self.resource
        table = resource.table
        tablename = resource.tablename

        T = current.T

        representation = r.representation

        output = dict()

        editable = self._config("editable", True)
        deletable = self._config("deletable", True)
        list_fields = self._config("list_fields")

        # List fields
        if not list_fields:
            fields = resource.readable_fields()
        else:
            fields = [table[f] for f in list_fields if f in table.fields]
        if not fields:
            fields = []
        if fields[0].name != table.fields[0]:
            fields.insert(0, table[table.fields[0]])

        # Get the target record ID
        record_id = self._record_id(r)

        # Check authorization to read the record
        authorised = self._permitted()
        if not authorised:
            r.unauthorised()

        if r.interactive:

            # If this is a single-component and no record exists,
            # try to create one if the user is permitted
            if not record_id and r.component and not r.multiple:
                authorised = self._permitted(method="create")
                if authorised:
                    return self.create(r, **attr)
                else:
                    return self.select(r, **attr)

            # Redirect to update if user has permission unless
            # a method has been specified in the URL
            if not r.method:
                authorised = self._permitted("update")
                if authorised and representation == "html" and editable:
                    return self.update(r, **attr)

            # Form configuration
            subheadings = self._config("subheadings")

            # Title and subtitle
            title = self.crud_string(r.tablename, "title_display")
            output.update(title=title)
            if r.component:
                subtitle = self.crud_string(tablename, "title_display")
                output.update(subtitle=subtitle)

            # Item
            if record_id:
                item = self.sqlform(record_id=record_id,
                                    readonly=True,
                                    format=representation)
                if subheadings:
                    self.insert_subheadings(item, self.tablename, subheadings)
            else:
                item = self.crud_string(tablename, "msg_list_empty")

            # View
            if representation == "html":
                response.view = self._view(r, "display.html")
                output.update(item=item)
            elif representation in ("popup", "iframe"):
                response.view = self._view(r, "popup.html")
                caller = attr.get("caller", None)
                output.update(form=item, caller=caller)

            # Buttons
            buttons = self.insert_buttons(r, "edit", "delete", "list",
                                          record_id=record_id)
            if buttons:
                output.update(buttons)

            # Last update
            last_update = self.last_update()
            if last_update:
                output.update(last_update)

        elif representation == "plain":
            # Hide empty fields from popups on map
            for field in table:
                if field.readable:
                    value = resource._rows.records[0][tablename][field.name]
                    if value is None or value == "" or value == []:
                        field.readable = False

            # Form
            item = self.sqlform(record_id=record_id,
                                readonly=True,
                                format=representation)
            output.update(item=item)

            # Edit Link
            EDIT = T("Edit")
            authorised = self._permitted(method="update")
            if authorised and editable:
                href_edit = r.url(method="update", representation="html")
                if href_edit:
                    edit_btn = A(EDIT, _href=href_edit,
                                 _id="edit-btn", _target="_blank")
                    output.update(edit_btn=edit_btn)

            response.view = "plain.html"

        elif representation == "csv":
            exporter = resource.exporter.csv
            return exporter(resource)

        elif representation == "map":
            exporter = S3MAP()
            return exporter(r, **attr)

        elif representation == "pdf":
            exporter = S3PDF()
            return exporter(r, **attr)

        elif representation == "xls":
            list_fields = self._config("list_fields")
            exporter = resource.exporter.xls
            return exporter(resource, list_fields=list_fields)

        elif representation == "json":
            exporter = S3Exporter(self.manager)
            return exporter.json(resource)

        else:
            r.error(501, self.manager.ERROR.BAD_FORMAT)

        return output

    # -------------------------------------------------------------------------
    def update(self, r, **attr):
        """
            Update a record

            @param r: the S3Request
            @param attr: dictionary of parameters for the method handler
        """

        session = current.session
        request = self.request
        response = current.response

        resource = self.resource
        table = resource.table
        tablename = resource.tablename

        T = current.T

        representation = r.representation

        output = dict()

        # Get table configuration
        editable = self._config("editable", True)
        deletable = self._config("deletable", True)

        # Get callbacks
        onvalidation = self._config("update_onvalidation") or \
                       self._config("onvalidation")
        onaccept = self._config("update_onaccept") or \
                   self._config("onaccept")

        # Get the target record ID
        record_id = self._record_id(r)
        if r.interactive and not record_id:
            r.error(404, self.resource.ERROR.BAD_RECORD)

        # Check if editable
        if not editable:
            if r.interactive:
                return self.read(r, **attr)
            else:
                r.error(400, self.resource.ERROR.BAD_METHOD)

        # Check permission for update
        authorised = self._permitted(method="update")
        if not authorised:
            r.unauthorised()

        if r.interactive:

            # Form configuration
            subheadings = self._config("subheadings")

            # Set view
            if representation == "html":
                response.view = self._view(r, "update.html")
            elif representation in ("popup", "iframe"):
                response.view = self._view(r, "popup.html")

            # Title and subtitle
            if r.component:
                title = self.crud_string(r.tablename, "title_display")
                subtitle = self.crud_string(self.tablename, "title_update")
                output.update(title=title, subtitle=subtitle)
            else:
                title = self.crud_string(self.tablename, "title_update")
                output.update(title=title)

            # Component join
            link = None
            if r.component:
                if resource.link is None:
                    pkey = resource.pkey
                    fkey = resource.fkey
                    table[fkey].comment = None
                    table[fkey].default = r.record[pkey]
                    table[fkey].update = r.record[pkey]
                    if r.http == "POST":
                        r.post_vars.update({fkey: r.record[pkey]})
                    table[fkey].readable = False
                    table[fkey].writable = False
                else:
                    link = Storage(resource = resource.link,
                                   master = r.record)

            # Success message
            message = self.crud_string(self.tablename, "msg_record_modified")

            # Get the form
            form = self.sqlform(record_id=record_id,
                                onvalidation=onvalidation,
                                onaccept=onaccept,
                                message=message,
                                link=link,
                                format=representation)

            # Insert subheadings
            if subheadings:
                self.insert_subheadings(form, tablename, subheadings)

            # Cancel button?
            if response.s3.cancel:
                form[0][-1][0].append(A(T("Cancel"),
                                        _href=response.s3.cancel,
                                        _class="action-lnk"))

            # Navigate-away confirmation
            if self.settings.navigate_away_confirm:
                form.append(SCRIPT("S3EnableNavigateAwayConfirm();"))

            # Put form into output
            output.update(form=form)

            # Add delete and list buttons
            buttons = self.insert_buttons(r, "delete",
                                          record_id=record_id)
            if buttons:
                output.update(buttons)

            # Last update
            last_update = self.last_update()
            if last_update:
                output.update(last_update)

            # Redirection
            update_next = self._config("update_next")
            if representation in ("popup", "iframe"):
                self.next = None
            elif not update_next:
                self.next = r.url(method="")
            else:
                try:
                    self.next = update_next(self)
                except TypeError:
                    self.next = update_next

        #elif representation == "plain":
            #pass

        elif representation == "url":
            return self.import_url(r)

        else:
            r.error(501, self.manager.ERROR.BAD_FORMAT)

        return output

    # -------------------------------------------------------------------------
    def delete(self, r, **attr):
        """
            Delete record(s)

            @param r: the S3Request
            @param attr: dictionary of parameters for the method handler

            @todo: update for link table components
        """

        session = current.session
        request = self.request
        response = current.response

        table = self.table
        tablename = self.tablename

        T = current.T

        representation = r.representation

        output = dict()

        # Get callback
        ondelete = self._config("ondelete")

        # Get table-specific parameters
        deletable = self._config("deletable", True)
        delete_next = self._config("delete_next", None)

        # Get the target record ID
        record_id = self._record_id(r)

        # Check if deletable
        if not deletable:
            r.error(403, self.manager.ERROR.NOT_PERMITTED,
                    next=r.url(method=""))

        # Check permission to delete
        authorised = self._permitted()
        if not authorised:
            r.unauthorised()

        elif r.interactive and r.http == "GET" and not record_id:
            # Provide a confirmation form and a record list
            form = FORM(TABLE(TR(
                        TD(self.settings.confirm_delete,
                           _style="color: red;"),
                        TD(INPUT(_type="submit", _value=T("Delete"),
                           _style="margin-left: 10px;")))))
            items = self.select(r, **attr).get("items", None)
            if isinstance(items, DIV):
                output.update(form=form)
            output.update(items=items)
            response.view = self._view(r, "delete.html")

        elif r.interactive and (r.http == "POST" or
                                r.http == "GET" and record_id):
            # Delete the records, notify success and redirect to the next view
            numrows = self.resource.delete(ondelete=ondelete,
                                           format=representation)
            if numrows > 1:
                message = "%s %s" % (numrows, T("records deleted"))
            elif numrows == 1:
                message = self.crud_string(self.tablename,
                                           "msg_record_deleted")
            else:
                r.error(404, self.manager.error, next=r.url(method=""))
            response.confirmation = message
            r.http = "DELETE" # must be set for immediate redirect
            self.next = delete_next or r.url(method="")

        elif r.http == "DELETE":
            # Delete the records and return a JSON message
            numrows = self.resource.delete(ondelete=ondelete,
                                           format=representation)
            if numrows > 1:
                message = "%s %s" % (numrows, T("records deleted"))
            elif numrows == 1:
                message = self.crud_string(self.tablename,
                                           "msg_record_deleted")
            else:
                r.error(404, self.manager.error, next=r.url(method=""))
            item = self.manager.xml.json_message(message=message)
            response.view = "xml.html"
            output.update(item=item)

        else:
            r.error(400, self.manager.ERROR.BAD_METHOD)

        return output

    # -------------------------------------------------------------------------
    def select(self, r, **attr):
        """
            Get a list view of the requested resource

            @param r: the S3Request
            @param attr: dictionary of parameters for the method handler
        """

        session = current.session
        request = self.request
        response = current.response

        table = self.table
        tablename = self.tablename

        representation = r.representation

        output = dict()

        # Get table-specific parameters
        orderby = self._config("orderby", None)
        sortby = self._config("sortby", [[1, 'asc']])
        linkto = self._config("linkto", None)
        insertable = self._config("insertable", True)
        listadd = self._config("listadd", True)
        addbtn = self._config("addbtn", False)
        list_fields = self._config("list_fields")
        report_groupby = self._config("report_groupby")
        report_hide_comments = self._config("report_hide_comments")

        # Check permission to read in this table
        authorised = self._permitted()
        if not authorised:
            r.unauthorised()

        # Pagination
        vars = request.get_vars
        if representation == "aadata":
            start = vars.get("iDisplayStart", None)
            limit = vars.get("iDisplayLength", None)
        else:
            start = vars.get("start", None)
            limit = vars.get("limit", None)
        if limit is not None:
            try:
                start = int(start)
                limit = int(limit)
            except ValueError:
                start = None
                limit = None # use default
        else:
            start = None # use default

        # Linkto
        if not linkto:
            linkto = self._linkto(r)

        # List fields
        if not list_fields:
            fields = self.resource.readable_fields()
            list_fields = [f.name for f in fields]
        else:
            fields = [table[f] for f in list_fields if f in table.fields]
        if not fields:
            fields = []

        if fields[0].name != table.fields[0]:
            fields.insert(0, table[table.fields[0]])
        if list_fields[0] != table.fields[0]:
            list_fields.insert(0, table.fields[0])

        # Truncate long texts
        if r.interactive or r.representation == "aadata":
            for f in self.table:
                if str(f.type) == "text" and not f.represent:
                    f.represent = self.truncate

        # Filter
        if response.s3.filter is not None:
            self.resource.add_filter(response.s3.filter)

        if r.interactive:

            left = []

            # SSPag?
            if not response.s3.no_sspag:
                limit = 1
                session.s3.filter = request.get_vars
                if orderby is None:
                    # Default initial sorting
                    scol = len(list_fields) > 1 and "1" or "0"
                    vars.update(iSortingCols="1",
                                iSortCol_0=scol,
                                sSortDir_0="asc")
                    orderby = self.ssp_orderby(table, list_fields, left=left)
                    del vars["iSortingCols"]
                    del vars["iSortCol_0"]
                    del vars["sSortDir_0"]
                if r.method == "search" and not orderby:
                    orderby = fields[0]

            # Custom view
            response.view = self._view(r, "list.html")

            if insertable:
                if listadd:
                    # Add a hidden add-form and a button to activate it
                    form = self.create(r, **attr).get("form", None)
                    if form is not None:
                        output.update(form=form)
                        addtitle = self.crud_string(tablename,
                                                    "subtitle_create")
                        output.update(addtitle=addtitle)
                        showadd_btn = self.crud_button(
                                            None,
                                            tablename=tablename,
                                            name="label_create_button",
                                            _id="show-add-btn")
                        output.update(showadd_btn=showadd_btn)
                        # Switch to list_create view
                        response.view = self._view(r, "list_create.html")

                elif addbtn:
                    # Add an action-button linked to the create view
                    buttons = self.insert_buttons(r, "add")
                    if buttons:
                        output.update(buttons)

            # Get the list
            items = self.sqltable(fields=list_fields,
                                  left=left,
                                  start=start,
                                  limit=limit,
                                  orderby=orderby,
                                  linkto=linkto,
                                  download_url=self.download_url,
                                  format=representation)

            # In SSPag, send the first 20 records together with the initial
            # response (avoids the dataTables Ajax request unless the user
            # tries nagivating around)
            if not response.s3.no_sspag and items:
                totalrows = self.resource.count()
                if totalrows:
                    if response.s3.dataTable_iDisplayLength:
                        limit = 2 * response.s3.dataTable_iDisplayLength
                    else:
                        limit = 20
                    aadata = dict(aaData = self.sqltable(
                                                left=left,
                                                fields=list_fields,
                                                start=0,
                                                limit=limit,
                                                orderby=orderby,
                                                linkto=linkto,
                                                download_url=self.download_url,
                                                as_page=True,
                                                format=representation) or [])
                    aadata.update(iTotalRecords=totalrows,
                                  iTotalDisplayRecords=totalrows)
                    response.aadata = json(aadata)
                    response.s3.start = 0
                    response.s3.limit = limit

            # Title and subtitle
            if r.component:
                title = self.crud_string(r.tablename, "title_display")
            else:
                title = self.crud_string(self.tablename, "title_list")
            subtitle = self.crud_string(self.tablename, "subtitle_list")
            output.update(title=title, subtitle=subtitle)

            # Empty table - or just no match?
            if not items:
                if "deleted" in self.table:
                    available_records = current.db(self.table.deleted == False)
                else:
                    available_records = current.db(self.table.id > 0)
                #if available_records.count():
                # This is faster:
                if available_records.select(self.table.id,
                                            limitby=(0, 1)).first():
                    items = self.crud_string(self.tablename, "msg_no_match")
                else:
                    items = self.crud_string(self.tablename, "msg_list_empty")
                if r.component and "showadd_btn" in output:
                    # Hide the list and show the form by default
                    del output["showadd_btn"]
                    del output["subtitle"]
                    items = ""
                    response.s3.no_formats = True

            # Update output
            output.update(items=items, sortby=sortby)

        elif representation == "aadata":

            left = []
            distinct = r.method == "search"

            # Get the master query for SSPag
            if session.s3.filter is not None:
                self.resource.build_query(filter=response.s3.filter,
                                          vars=session.s3.filter)

            displayrows = totalrows = self.resource.count(distinct=distinct)

            # SSPag dynamic filter?
            if vars.sSearch:
                squery = self.ssp_filter(table,
                                         fields=list_fields,
                                         left=left)
                if squery is not None:
                    self.resource.add_filter(squery)
                    displayrows = self.resource.count(left=left,
                                                      distinct=distinct)

            # SSPag sorting
            if vars.iSortingCols and orderby is None:
                orderby = self.ssp_orderby(table, list_fields, left=left)
            if r.method == "search" and not orderby:
                orderby = fields[0]

            # Echo
            sEcho = int(vars.sEcho or 0)

            # Get the list
            items = self.sqltable(fields=list_fields,
                                  left=left,
                                  distinct=distinct,
                                  start=start,
                                  limit=limit,
                                  orderby=orderby,
                                  linkto=linkto,
                                  download_url=self.download_url,
                                  as_page=True,
                                  format=representation) or []

            result = dict(sEcho = sEcho,
                          iTotalRecords = totalrows,
                          iTotalDisplayRecords = displayrows,
                          aaData = items)

            output = json(result)

        elif representation == "plain":
            items = self.sqltable(fields=list_fields,
                                  as_list=True)
            response.view = "plain.html"
            return dict(item=items)

        elif representation == "csv":
            exporter = S3Exporter(self.manager)
            return exporter.csv(self.resource)

        elif representation == "map":
            exporter = S3MAP()
            return exporter(r, **attr)

        elif representation == "pdf":
            exporter = S3PDF()
            return exporter(r, **attr)

        elif representation == "xls":
            exporter = S3Exporter(self.manager)
            return exporter.xls(self.resource,
                                list_fields=list_fields,
                                report_groupby=report_groupby)

        elif representation == "json":
            exporter = S3Exporter(self.manager)
            return exporter.json(self.resource,
                                 start=start,
                                 limit=limit,
                                 fields=fields,
                                 orderby=orderby)

        else:
            r.error(501, self.manager.ERROR.BAD_FORMAT)

        return output

    # -------------------------------------------------------------------------
    def upload(self, r, **attr):
        """
            Upload new records

            @param r: the S3Request
            @param attr: dictionary of parameters for the method handler
        """

        representation = r.representation

        # Check permission for create
        authorised = self._permitted(method="create")
        if not authorised:
            if r.method is not None:
                r.unauthorised()
            else:
                return dict(form=None)

        if representation == "pdf":
            exporter = S3PDF()
            return exporter(r, **attr)

        else:
            r.error(501, self.manager.ERROR.BAD_FORMAT)

        return output

    # -------------------------------------------------------------------------
    # Utility functions
    # -------------------------------------------------------------------------
    def sqltable(self,
                 fields=None,
                 start=0,
                 limit=None,
                 left=None,
                 orderby=None,
                 distinct=False,
                 linkto=None,
                 download_url=None,
                 no_ids=False,
                 as_page=False,
                 as_list=False,
                 format=None):
        """
            DRY helper function for SQLTABLEs in CRUD

            @param fields: list of fieldnames to display
            @param start: index of the first record to display
            @param limit: maximum number of records to display
            @param left: left outer joins
            @param orderby: orderby for the query
            @param distinct: distinct for the query
            @param linkto: hook to link record IDs
            @param download_url: the default download URL of the application
            @param as_page: return the list as JSON page
            @param as_list: return the list as Python list
            @param format: the representation format
        """

        db = current.db
        resource = self.resource
        table = resource.table

        if fields is None:
            fields = [f.name for f in resource.readable_fields()]
        if table._id.name not in fields and not no_ids:
            fields.insert(0, table._id.name)
        lfields, joins = self.get_list_fields(table, fields)

        colnames = [f.colname for f in lfields]
        headers = dict(map(lambda f: (f.colname, f.label), lfields))

        attributes = dict(distinct=distinct)
        # Orderby
        if orderby is not None:
            attributes.update(orderby=orderby)
        # Slice
        limitby = resource.limitby(start=start, limit=limit)
        if limitby is not None:
            attributes.update(limitby=limitby)
        # Joins
        query = resource.get_query()
        for j in joins.values():
            query &= j
        # Left outer joins
        if left is not None:
            attributes.update(left=left)

        # Fields in the query
        qfields = [f.field for f in lfields if f.field is not None]
        if no_ids:
            qfields.insert(0, table._id)

        # Add orderby fields which are not in qfields
        if distinct and orderby is not None:
            qf = [str(f) for f in qfields]
            if isinstance(orderby, str):
                of = orderby.split(",")
            elif not isinstance(orderby, (list, tuple)):
                of = [orderby]
            else:
                of = orderby
            for e in of:
                if isinstance(e, Field) and str(e) not in qf:
                    qfields.append(e)
                    qf.append(str(e))
                elif isinstance(e, str):
                    fn = e.strip().split()[0].split(".", 1)
                    tn, fn = ([table._tablename] + fn)[-2:]
                    try:
                        t = db[tn]
                        f = t[fn]
                    except:
                        continue
                    if str(f) not in qf:
                        qfields.append(f)
                        qf.append(str(e))

        # Retrieve the rows
        rows = db(query).select(*qfields, **attributes)
        if not rows:
            return None

        # Fields to show
        row = rows.first()
        def __expand(tablename, row, lfields=lfields):
            columns = []
            for f in lfields:
                if f.tname in row and isinstance(row[f.tname], Row):
                    columns += __expand(f.tname, lfields)
                elif (f.tname, f.fname) not in columns and f.fname in row:
                    columns.append((f.tname, f.fname))
            return columns
        columns = __expand(table._tablename, row)
        lfields = [lf for lf in lfields
                   if lf.show and (lf.tname, lf.fname) in columns]
        colnames = [f.colname for f in lfields]
        rows.colnames = colnames

        # Representation
        def __represent(f, row, columns=columns):
            if f.field:
                return self.manager.represent(f.field,
                                              record=row, linkto=linkto)
            else:
                if (f.tname, f.fname) in columns:
                    if f.tname in row and f.fname in row[f.tname]:
                        return str(row[f.tname][f.fname])
                    elif f.fname in row:
                        return str(row[f.fname])
                    else:
                        return None
                else:
                    return None

        # Render as...
        if as_page:
            # ...JSON page (for pagination)
            items = [[__represent(f, row) for f in lfields] for row in rows]
        elif as_list:
            # ...Python list
            items = rows.as_list()
        else:
            # ...SQLTABLE
            items = SQLTABLES3(rows,
                               headers=headers,
                               linkto=linkto,
                               upload=download_url,
                               _id="list",
                               _class="dataTable display")
        return items

    # -------------------------------------------------------------------------
    def sqlform(self,
                record_id=None,
                readonly=False,
                from_table=None,
                from_record=None,
                map_fields=None,
                link=None,
                onvalidation=None,
                onaccept=None,
                message="Record created/updated",
                format=None):
        """
            DRY helper function for SQLFORMs in CRUD

            @todo: parameter docstring?
        """

        # Environment
        session = current.session
        request = self.request
        response = current.response

        # Get the CRUD settings
        audit = self.manager.audit
        s3 = self.manager.s3
        settings = s3.crud

        # Table and model
        prefix = self.prefix
        name = self.name
        tablename = self.tablename
        table = self.table
        model = self.manager.model

        record = None
        labels = None

        if not readonly:

            # Pre-populate from a previous record?
            if record_id is None and from_table is not None:
                # Field mapping
                if map_fields:
                    if isinstance(map_fields, dict):
                        fields = [from_table[map_fields[f]]
                                for f in map_fields
                                    if f in table.fields and
                                    map_fields[f] in from_table.fields and
                                    table[f].writable]
                    elif isinstance(map_fields, (list, tuple)):
                        fields = [from_table[f]
                                for f in map_fields
                                    if f in table.fields and
                                    f in from_table.fields and
                                    table[f].writable]
                    else:
                        raise TypeError
                else:
                    fields = [from_table[f]
                              for f in table.fields
                              if f in from_table.fields and table[f].writable]
                # Audit read => this is a read method, finally
                audit = self.manager.audit
                prefix, name = from_table._tablename.split("_", 1)
                audit("read", prefix, name,
                      record=from_record, representation=format)
                # Get original record
                query = (from_table.id == from_record)
                row = current.db(query).select(limitby=(0, 1), *fields).first()
                if row:
                    if isinstance(map_fields, dict):
                        record = Storage([(f, row[map_fields[f]])
                                          for f in map_fields])
                    else:
                        record = Storage(row)

            # Pre-populate from call?
            elif record_id is None and isinstance(self.data, dict):
                record = Storage([(f, self.data[f])
                                  for f in self.data
                                  if f in table.fields and table[f].writable])

            # Add missing fields to pre-populated record
            if record:
                missing_fields = Storage()
                for f in table.fields:
                    if f not in record and table[f].writable:
                        missing_fields[f] = table[f].default
                record.update(missing_fields)
                record.update(id=None)

            # Add asterisk to labels of required fields
            mark_required = self._config("mark_required")
            labels, required = s3_mark_required(table, mark_required)
            if required:
                # Show the key if there are any required fields.
                response.s3.has_required = True
            else:
                response.s3.has_required = False

        if record is None:
            record = record_id

        if format == "plain":
            # Default formstyle works best when we have no formatting
            formstyle = "table3cols"
        else:
            formstyle = settings.formstyle

        # Get the form
        form = SQLFORM(table,
                       record = record,
                       record_id = record_id,
                       readonly = readonly,
                       comments = not readonly,
                       deletable = False,
                       showid = False,
                       upload = self.download_url,
                       labels = labels,
                       formstyle = formstyle,
                       separator = "",
                       submit_button = settings.submit_button)

        # Style the Submit button, if-requested
        if settings.submit_style:
            try:
                form[0][-1][0][0]["_class"] = settings.submit_style
            except TypeError:
                # Submit button has been removed
                pass

        # Process the form
        logged = False
        if not readonly:
            # Set form name
            formname = "%s/%s" % (self.tablename, form.record_id)

            # Get the proper onvalidation routine
            if isinstance(onvalidation, dict):
                onvalidation = onvalidation.get(self.tablename, [])

            if form.accepts(request.post_vars,
                            session,
                            formname=formname,
                            onvalidation=onvalidation,
                            keepvalues=False,
                            hideerror=False):

                # Message
                response.flash = message

                # Audit
                if record_id is None:
                    audit("create", prefix, name, form=form,
                          representation=format)
                else:
                    audit("update", prefix, name, form=form,
                          record=record_id, representation=format)
                logged = True

                # Update super entity links
                model.update_super(table, form.vars)

                # Update component link
                if link:
                    resource = link.resource
                    master = link.master
                    resource.update_link(master, form.vars)

                # Set record ownership properly
                if form.vars.id and record_id is None:
                    self.manager.auth.s3_set_record_owner(table,
                                                          form.vars.id)

                # Store session vars
                if form.vars.id:
                    if record_id is None:
                        self.manager.auth.s3_make_session_owner(table,
                                                                form.vars.id)
                    self.resource.lastid = str(form.vars.id)
                    self.manager.store_session(prefix, name, form.vars.id)

                # Execute onaccept
                callback(onaccept, form, tablename=tablename)

        if not logged and not form.errors:
            audit("read", prefix, name,
                  record=record_id, representation=format)

        return form

    # -------------------------------------------------------------------------
    def crud_button(self, label,
                    tablename=None,
                    name=None,
                    _href=None,
                    _id=None,
                    _class="action-btn"):
        """
            Generate a CRUD action button

            @param label: the link label (None if using CRUD string)
            @param tablename: the name of table for CRUD string selection
            @param name: name of CRUD string for the button label
            @param _href: the target URL
            @param _id: the HTML-ID of the link
            @param _class: the HTML-class of the link
        """

        if name:
            labelstr = self.crud_string(tablename, name)
        else:
            labelstr = str(label)
        if not _href:
            button = A(labelstr, _id=_id, _class=_class)
        else:
            button = A(labelstr, _href=_href, _id=_id, _class=_class)
        return button

    # -------------------------------------------------------------------------
    @staticmethod
    def crud_string(tablename, name):
        """
        Get a CRUD info string for interactive pages

        @param tablename: the table name
        @param name: the name of the CRUD string

        """

        s3 = current.manager.s3

        crud_strings = s3.crud_strings.get(tablename, s3.crud_strings)
        not_found = s3.crud_strings.get(name, None)

        return crud_strings.get(name, not_found)

    # -------------------------------------------------------------------------
    def last_update(self):
        """
            Get the last update meta-data
        """

        db = current.db
        table = self.table
        record_id = self.record

        T = current.T

        output = dict()

        if record_id:
            fields = []
            if "modified_on" in table.fields:
                fields.append(table.modified_on)
            if "modified_by" in table.fields:
                fields.append(table.modified_by)

            query = table.id==record_id
            record = db(query).select(limitby=(0, 1), *fields).first()

            try:
                represent = table.modified_by.represent
            except:
                # Table doesn't have a modified_by field
                represent = ""

            # @todo: "on" and "by" particles are problematic in translations
            if "modified_by" in record and represent:
                if not record.modified_by:
                    modified_by = T("anonymous user")
                else:
                    modified_by = represent(record.modified_by)
                output.update(modified_by= T("by %(person)s") % 
                                           dict(person = modified_by))
            if "modified_on" in record:
                output.update(modified_on=T("on %(date)s") %
                              dict(date = record.modified_on))

        return output

    # -------------------------------------------------------------------------
    def truncate(self, text, length=48, nice=True):
        """
            Nice truncating of text

            @param text: the text
            @param length: the desired maximum length of the output
            @param nice: don't truncate in the middle of a word
        """

        if text is None:
            return ""

        if len(text) > length:
            l = length - 3
            if nice:
                return "%s..." % text[:l].rsplit(" ", 1)[0][:l]
            else:
                return "%s..." % text[:l]
        else:
            return text

    # -------------------------------------------------------------------------
    @staticmethod
    def insert_subheadings(form, tablename, subheadings):
        """
            Insert subheadings into forms

            @param form: the form
            @param tablename: the tablename
            @param subheadings: a dict of {"Headline": Fieldnames}, where
                Fieldname can be either a single field name or a list/tuple
                of field names belonging under that headline
        """

        if subheadings:
            if tablename in subheadings:
                subheadings = subheadings.get(tablename)
            form_rows = iter(form[0])
            tr = form_rows.next()
            i = 0
            done = []
            while tr:
                f = tr.attributes.get("_id", None)
                if f.startswith(tablename):
                    f = f[len(tablename)+1:-6]
                    for k in subheadings.keys():
                        if k in done:
                            continue
                        fields = subheadings[k]
                        if not isinstance(fields, (list, tuple)):
                            fields = [fields]
                        if f in fields:
                            done.append(k)
                            form[0].insert(i, TR(TD(k, _colspan=3,
                                                    _class="subheading"),
                                                 _class = "subheading",
                                                 _id = "%s_%s__subheading" %
                                                       (tablename, f)))
                            tr.attributes.update(_class="after_subheading")
                            tr = form_rows.next()
                            i += 1
                try:
                    tr = form_rows.next()
                except StopIteration:
                    break
                else:
                    i += 1

    # -------------------------------------------------------------------------
    def insert_buttons(self, r, *buttons, **attr):
        """
            Insert resource action buttons

            @param r: the S3Request
            @param buttons: button names ("add", "edit", "delete", "list")
            @keyword record_id: the record ID
        """

        output = dict()

        T = current.T

        tablename = self.tablename
        representation = r.representation

        record_id = attr.get("record_id", None)

        # Button labels
        ADD = self.crud_string(tablename, "label_create_button")
        EDIT = T("Edit")
        DELETE = self.crud_string(tablename, "label_delete_button")
        LIST = self.crud_string(tablename, "label_list_button")

        # Button URLs
        href_add = r.url(method="create", representation=representation)
        href_edit = r.url(method="update", representation=representation)
        href_delete = r.url(method="delete", representation=representation)
        href_list = r.url(method="")

        # Table CRUD configuration
        insertable = self._config("insertable", True)
        editable = self._config("editable", True)
        deletable = self._config("deletable", True)

        # Add button
        if "add" in buttons:
            authorised = self._permitted(method="create")
            if authorised and href_add and insertable:
                add_btn = self.crud_button(ADD, _href=href_add, _id="add-btn")
                output.update(add_btn=add_btn)

        # List button
        if "list" in buttons:
            if not r.component or r.multiple:
                list_btn = self.crud_button(LIST, _href=href_list,
                                            _id="list-btn")
                output.update(list_btn=list_btn)

        if not record_id:
            return output

        # Edit button
        if "edit" in buttons:
            authorised = self._permitted(method="update")
            if authorised and href_edit and editable and r.method != "update":
                edit_btn = self.crud_button(EDIT, _href=href_edit,
                                            _id="edit-btn")
                output.update(edit_btn=edit_btn)

        # Delete button
        if "delete" in buttons:
            authorised = self._permitted(method="delete")
            if authorised and href_delete and deletable:
                delete_btn = self.crud_button(DELETE, _href=href_delete,
                                              _id="delete-btn",
                                              _class="delete-btn")
                output.update(delete_btn=delete_btn)

        return output

    # -------------------------------------------------------------------------
    @staticmethod
    def action_button(label, url, **attr):
        """
            Add a link to response.s3.actions

            @param label: the link label
            @param url: the target URL
            @param attr: attributes for the link (default: {"_class":"action-btn"})
        """

        response = current.response

        link = dict(attr)
        link.update(label=str(label), url=url)
        if "_class" not in link:
            link.update(_class="action-btn")

        if response.s3.actions is None:
            response.s3.actions = [link]
        else:
            response.s3.actions.append(link)

    # -------------------------------------------------------------------------
    @staticmethod
    def action_buttons(r,
                       deletable=True,
                       editable=True,
                       copyable=False,
                       read_url=None,
                       delete_url=None,
                       update_url=None,
                       copy_url=None):
        """
            Provide the usual action buttons in list views.
            Allow customizing the urls, since this overwrites anything
            that would be inserted by CRUD/select via linkto. The resource
            id should be represented by "[id]".

            @param r: the S3Request
            @param deletable: records can be deleted
            @param editable: records can be modified
            @param copyable: record data can be copied into new record
            @param read_url: URL to read a record
            @param delete_url: URL to delete a record
            @param update_url: URL to update a record
            @param copy_url: URL to copy record data

            @note: If custom actions are already configured at this point,
                   they will appear AFTER the standard action buttons
        """

        s3crud = S3CRUD
        labels = current.manager.LABEL

        db = current.db
        response = current.response
        custom_actions = response.s3.actions
        response.s3.actions = None

        auth = current.auth
        has_permission = auth.s3_has_permission
        ownership_required = auth.permission.ownership_required

        if r.component:
            table = r.component.table
            args = [r.id, r.component.alias, "[id]"]
        else:
            table = r.table
            args = ["[id]"]

        # Open-action (Update or Read)
        if editable and has_permission("update", table) and \
        not auth.permission.ownership_required(table, "update"):
            if not update_url:
                update_url = URL(args = args + ["update"])
            s3crud.action_button(labels.UPDATE, update_url)
        else:
            if not read_url:
                read_url = URL(args = args)
            s3crud.action_button(labels.READ, read_url)

        # Delete-action
        if deletable and has_permission("delete", table):
            if not delete_url:
                delete_url = URL(args = args + ["delete"])
            if auth.permission.ownership_required(table, "delete"):
                # Check which records can be deleted
                query = auth.s3_accessible_query("delete", table)
                rows = db(query).select(table.id)
                restrict = [str(row.id) for row in rows]
                s3crud.action_button(labels.DELETE, delete_url,
                                     _class="delete-btn", restrict=restrict)
            else:
                s3crud.action_button(labels.DELETE, delete_url,
                                     _class="delete-btn")

        # Copy-action
        if copyable and has_permission("create", table):
            if not copy_url:
                copy_url = URL(args = args + ["copy"])
            s3crud.action_button(labels.COPY, copy_url)

        # Append custom actions
        if custom_actions:
            response.s3.actions = response.s3.actions + custom_actions

        return

    # -------------------------------------------------------------------------
    def import_csv(self, file, table=None):
        """
            Import CSV file into database

            @param file: file handle
            @param table: the table to import to
        """

        if table:
            table.import_from_csv_file(file)
        else:
            db = current.db
            # This is the preferred method as it updates reference fields
            db.import_from_csv_file(file)
            db.commit()

    # -------------------------------------------------------------------------
    def import_url(self, r):
        """
            Import data from URL query

            @param r: the S3Request
            @note: can only update single records (no mass-update)

            @todo: update for link table components
            @todo: re-integrate into S3Importer
        """

        manager = self.manager
        xml = manager.xml

        prefix, name, table, tablename = r.target()

        record = r.record
        resource = r.resource

        # Handle components
        if record and r.component:
            resource = resource.components[r.component_name]
            resource.load()
            if len(resource) == 1:
                record = resource.records()[0]
            else:
                record = None
            r.vars.update({resource.fkey: r.record[resource.pkey]})
        elif not record and r.component:
            item = xml.json_message(False, 400, "Invalid Request!")
            return dict(item=item)

        # Check for update
        if record and xml.UID in table.fields:
            r.vars.update({xml.UID: xml.export_uid(record[xml.UID])})

        # Build tree
        element = etree.Element(xml.TAG.resource)
        element.set(xml.ATTRIBUTE.name, resource.tablename)
        for var in r.vars:
            if var.find(".") != -1:
                continue
            elif var in table.fields:
                field = table[var]
                value = str(r.vars[var]).decode("utf-8")
                if var in xml.FIELDS_TO_ATTRIBUTES:
                    element.set(var, value)
                else:
                    data = etree.Element(xml.TAG.data)
                    data.set(xml.ATTRIBUTE.field, var)
                    if field.type == "upload":
                        data.set(xml.ATTRIBUTE.filename, value)
                    else:
                        data.text = xml.xml_encode(value)
                    element.append(data)
        tree = xml.tree([element], domain=manager.domain)

        # Import data
        result = Storage(committed=False)
        manager.log = lambda job, result=result: result.update(job=job)
        try:
            success = resource.import_xml(tree)
        except SyntaxError:
            pass

        # Check result
        if result.job:
            result = result.job

        # Build response
        if success and result.committed:
            id = result.id
            method = result.method
            if method == result.METHOD.CREATE:
                item = xml.json_message(True, 201, "Created as %s?%s.id=%s" %
                        (str(r.url(method="",
                                   representation="html",
                                   vars=dict(),
                                  )
                            ),
                         result.name, result.id)
                        )
            else:
                item = xml.json_message(True, 200, "Record updated")
        else:
            item = xml.json_message(False, 403,
                        "Could not create/update record: %s" %
                            resource.error or xml.error,
                        tree=xml.tree2json(tree))

        return dict(item=item)

    # -------------------------------------------------------------------------
    def _linkto(self, r, authorised=None, update=None, native=False):
        """
            Returns a linker function for the record ID column in list views

            @param r: the S3Request
            @param authorised: user authorised for update
                (override internal check)
            @param update: provide link to update rather than to read
            @param native: link to the native controller rather than to
                component controller
        """

        c = None
        f = None

        response = current.response

        prefix, name, table, tablename = r.target()
        permit = current.auth.s3_has_permission
        model = r.manager.model

        if authorised is None:
            authorised = permit("update", tablename)

        if authorised and update:
            linkto = model.get_config(tablename, "linkto_update", None)
        else:
            linkto = model.get_config(tablename, "linkto", None)

        if r.component and native:
            # link to native component controller (be sure that you have one)
            c = prefix
            f = name

        def list_linkto(record_id, r=r, c=c, f=f,
                        linkto=linkto,
                        update=authorised and update):

            if linkto:
                try:
                    url = str(linkto(record_id))
                except TypeError:
                    url = linkto % record_id
                return url
            else:
                if r.component:
                    if r.link and not r.actuate_link():
                        # We're rendering a link table here, but must
                        # however link to the component record IDs
                        if str(record_id).isdigit():
                            # dataTables uses the value in the ID column
                            # to render action buttons, so we replace that
                            # value by the component record ID using .represent
                            _id = r.link.table._id
                            _id.represent = lambda opt, \
                                                   link=r.link, master=r.id: \
                                                   link.component_id(master, opt)
                            # The native link behind the action buttons uses
                            # record_id, so we replace that too just in case
                            # the action button cannot be displayed
                            record_id = r.link.component_id(r.id, record_id)
                    if c and f:
                        args = [record_id]
                    else:
                        c = r.controller
                        f = r.function
                        args = [r.id, r.component_name, record_id]
                    if update:
                        return str(URL(r=r, c=c, f=f,
                                       args=args + ["update"],
                                       vars=r.vars))
                    else:
                        return str(URL(r=r, c=c, f=f,
                                       args=args,
                                       vars=r.vars))
                else:
                    args = [record_id]
                    if update:
                        return str(URL(r=r, c=c, f=f,
                                       args=args + ["update"]))
                    else:
                        return str(URL(r=r, c=c, f=f,
                                       args=args))
        return list_linkto

    # -------------------------------------------------------------------------
    def ssp_filter(self, table, fields, left=[]):
        """
            Convert the SSPag GET vars into a filter query

            @param table: the table
            @param fields: list of field names as displayed in the
                           list view (same order!)
            @param left: list of left joins
        """

        vars = self.request.get_vars

        context = str(vars.sSearch).lower()
        columns = int(vars.iColumns)

        wildcard = "%%%s%%" % context

        # Retrieve the list of search fields
        lfields, joins = self.get_list_fields(table, fields)
        flist = []
        for i in xrange(0, columns):
            field = lfields[i].field
            if not field:
                continue
            fieldtype = str(field.type)
            if fieldtype.startswith("reference") and \
               hasattr(field, "sortby") and field.sortby:
                tn = fieldtype[10:]
                try:
                    join = [j for j in left if j.first._tablename == tn]
                except:
                    # Old DAL version?
                    join = [j for j in left if j.table._tablename == tn]
                if not join:
                    left.append(current.db[tn].on(field == current.db[tn].id))
                else:
                    join[0].query = (join[0].query) | (field == current.db[tn].id)
                if isinstance(field.sortby, (list, tuple)):
                    flist.extend([current.db[tn][f] for f in field.sortby])
                else:
                    if field.sortby in current.db[tn]:
                        flist.append(current.db[tn][field.sortby])
            else:
                flist.append(field)

        # Build search query
        searchq = None
        for field in flist:
            query = None
            ftype = str(field.type)
            if ftype in ("integer", "list:integer", "list:string") or \
               ftype.startswith("list:reference") or \
               ftype.startswith("reference"):
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
                        continue
                    vlist = []
                    for (value, text) in options:
                        if str(text).lower().find(context) != -1:
                            vlist.append(value)
                    if vlist:
                        query = field.belongs(vlist)
                else:
                    continue
            elif str(field.type) in ("string", "text"):
                query = field.lower().like(wildcard)
            if searchq is None and query:
                searchq = query
            elif query:
                searchq = searchq | query
        for j in joins.values():
            if searchq is None:
                searchq = j
            else:
                searchq &= j

        return searchq

    # -------------------------------------------------------------------------
    def ssp_orderby(self, table, fields, left=[]):
        """
            Convert the SSPag GET vars into a sorting query

            @param table: the table
            @param fields: list of field names as displayed
                           in the list view (same order!)
            @param left: list of left joins
        """

        vars = self.request.get_vars
        tablename = table._tablename

        iSortingCols = int(vars["iSortingCols"])

        def direction(i):
            dir = vars["sSortDir_%s" % str(i)]
            return dir and " %s" % dir or ""

        orderby = []

        lfields, joins = self.get_list_fields(table, fields)
        columns = [lfields[int(vars["iSortCol_%s" % str(i)])].field
                   for i in xrange(iSortingCols)]
        for i in xrange(len(columns)):
            c = columns[i]
            if not c:
                continue
            fieldtype = str(c.type)
            if fieldtype.startswith("reference") and \
               hasattr(c, "sortby") and c.sortby:
                tn = fieldtype[10:]
                try:
                    join = [j for j in left if j.first._tablename == tn]
                except:
                    # Old DAL version?
                    join = [j for j in left if j.table._tablename == tn]
                if not join:
                    left.append(current.db[tn].on(c == current.db[tn].id))
                else:
                    try:
                        join[0].query = (join[0].second) | \
                                        (c == current.db[tn].id)
                    except:
                        # Old DAL version?
                        join[0].query = (join[0].query) | \
                                        (c == current.db[tn].id)
                if not isinstance(c.sortby, (list, tuple)):
                    orderby.append("%s.%s%s" % (tn, c.sortby, direction(i)))
                else:
                    orderby.append(", ".join(["%s.%s%s" %
                                              (tn, fn, direction(i))
                                              for fn in c.sortby]))
            else:
                orderby.append("%s%s" % (c, direction(i)))

        return ", ".join(orderby)

    # -------------------------------------------------------------------------
    def get_list_fields(self, table, fields):
        """
            Helper to resolve list_fields

            @param table: the table
            @param fields: the list_fields array
        """

        db = current.db
        tablename = table._tablename

        joins = dict()
        lfields = []

        # Collect the extra fields
        flist = list(fields)
        for vtable in table.virtualfields:
            try:
                extra_fields = vtable.extra_fields
                for ef in extra_fields:
                    if ef not in flist:
                        flist.append(ef)
            except:
                continue

        for f in flist:
            # Allow to override the field label
            if isinstance(f, tuple):
                label, fieldname = f
            else:
                label, fieldname = None, f
            field = None
            tname = tablename
            fname = fieldname
            if "$" in fieldname:
                # Field in referenced table
                fk, fname = fieldname.split("$", 1)
                if fk in table.fields:
                    ftype = str(table[fk].type)
                    if ftype[:9] == "reference":
                        tname = ftype[10:]
                        ftable = db[tname]
                        if fname in ftable.fields:
                            field = ftable[fname]
                            if fk not in joins:
                                join = (table[fk] == ftable._id)
                                if "deleted" in ftable.fields:
                                    join &= (ftable.deleted != True)
                                joins[fk] = join
                if field is None:
                    continue
                if label is None:
                    label = field.label
            elif fieldname in table.fields:
                # Field in this table
                field = table[fieldname]
                if label is None:
                    label = field.label
            else:
                # Virtual field?
                if label is None:
                    label = fname.capitalize()
            colname = "%s.%s" % (tname, fname)
            lfields.append(Storage(fieldname = fieldname,
                                   tname = tname,
                                   fname = fname,
                                   colname = colname,
                                   field = field,
                                   label = label,
                                   show = f in fields))

        return (lfields, joins)

# END
# *****************************************************************************

