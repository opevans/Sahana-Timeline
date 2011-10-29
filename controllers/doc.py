# -*- coding: utf-8 -*-

"""
    Document Library - Controllers

    @author: Fran Boon
    @author: Michael Howden
"""

module = request.controller

if module not in deployment_settings.modules:
    raise HTTP(404, body="Module disabled: %s" % module)

# Options Menu (available in all Functions' Views)
s3_menu(module)

# =============================================================================
def index():
    "Module's Home Page"

    module_name = deployment_settings.modules[module].name_nice
    response.title = module_name
    return dict(module_name=module_name)

# =============================================================================
def document():
    """ RESTful CRUD controller """

    resourcename = request.function

    # Load Models
    s3mgr.load("doc_document")

    rheader = lambda r: document_rheader(r)

    output = s3_rest_controller(module, resourcename,
                                rheader=rheader)

    return output

# -----------------------------------------------------------------------------
def document_rheader(r):
    if r.representation == "html":
        doc_document = r.record
        if doc_document:
            #rheader_tabs = s3_rheader_tabs(r, document_tabs(r))
            table = db.doc_document
            rheader = DIV(B("%s: " % T("Name")),doc_document.name,
                        TABLE(TR(
                                TH("%s: " % T("File")), table.file.represent( doc_document.file ),
                                TH("%s: " % T("URL")), table.url.represent( doc_document.url ),
                                ),
                                TR(
                                TH("%s: " % T("Organization")), table.organisation_id.represent( doc_document.organisation_id ),
                                TH("%s: " % T("Person")), table.person_id.represent( doc_document.organisation_id ),
                                ),
                            ),
                        #rheader_tabs
                        )
            return rheader
    return None

# -----------------------------------------------------------------------------
def document_tabs(r):
    """
        Display the number of Components in the tabs
        - currently unused as we don't have these tabs off documents
    """

    tab_opts = [{"tablename": "assess_rat",
                 "resource": "rat",
                 "one_title": T("1 Assessment"),
                 "num_title": " Assessments",
                },
                {"tablename": "irs_ireport",
                 "resource": "ireport",
                 "one_title": "1 Incident Report",
                 "num_title": " Incident Reports",
                },
                {"tablename": "cr_shelter",
                 "resource": "shelter",
                 "one_title": "1 Shelter",
                 "num_title": " Shelters",
                },
                #{"tablename": "flood_freport",
                # "resource": "freport",
                # "one_title": "1 Flood Report",
                # "num_title": " Flood Reports",
                #},
                {"tablename": "req_req",
                 "resource": "req",
                 "one_title": "1 Request",
                 "num_title": " Requests",
                },
                ]
    tabs = [(T("Details"), None)]
    for tab_opt in tab_opts:
        tablename = tab_opt["tablename"]
        if tablename in db and document_id in db[tablename]:
            tab_count = db( (db[tablename].deleted == False) & (db[tablename].document_id == r.id) ).count()
            if tab_count == 0:
                label = s3base.S3CRUD.crud_string(tablename, "title_create")
            elif tab_count == 1:
                label = tab_opt["one_title"]
            else:
                label = T(str(tab_count) + tab_opt["num_title"] )
            tabs.append( (label, tab_opt["resource"] ) )

    return tabs

# =============================================================================
def image():
    """ RESTful CRUD controller """

    resourcename = request.function

    # Load Models
    s3mgr.load("doc_document")

    output = s3_rest_controller(module, resourcename)

    return output
# =============================================================================
def bulk_upload():
    """
        Custom view to allow bulk uploading of Photos

        @ToDo: Allow creation of a GIS Feature Layer to view on the map
        @ToDo: Allow uploading of associated GPX track for timestamp correlation.
        See r1595 for the previous draft of this work
    """

    response.s3.stylesheets.append( "S3/fileuploader.css" )
    return dict()

def upload_bulk():
    """
        Receive the Uploaded data from bulk_upload()

        https://github.com/valums/file-uploader/blob/master/server/readme.txt

        @ToDo: Read EXIF headers to geolocate the Photos
    """

    # Load Models
    s3mgr.load("doc_document")

    tablename = "doc_image"
    table = db[tablename]

    import cgi

    source = request.post_vars.get("qqfile", None)
    if isinstance(source, cgi.FieldStorage) and source.filename:
        # For IE6-8, Opera, older versions of other browsers you get the file as you normally do with regular form-base uploads.
        name = source.filename
        image = source.file

    else:
        # For browsers which upload file with progress bar, you will need to get the raw post data and write it to the file.
        if "name" in request.vars:
            name = request.vars.name
        else:
            HTTP(400, "Invalid Request: Need a Name!")

        image = request.body.read()
        # Convert to StringIO for onvalidation/import
        import cStringIO
        image = cStringIO.StringIO(image)
        source = Storage()
        source.filename = name
        source.file = image

    form = SQLFORM(table)
    vars = Storage()
    vars.name = name
    vars.image = source
    vars._formname = "%s_create" % tablename

    # onvalidation callback
    onvalidation = s3mgr.model.get_config(tablename, "create_onvalidation",
                   s3mgr.model.get_config(tablename, "onvalidation"))

    if form.accepts(vars, onvalidation=onvalidation):
        msg = Storage(success = True)
        # onaccept callback
        onaccept = s3mgr.model.get_config(tablename, "create_onaccept",
                   s3mgr.model.get_config(tablename, "onaccept"))
        callback(onaccept, form, tablename=tablename)
    else:
        error_msg = ""
        for error in form.errors:
            error_msg = "%s\n%s:%s" % (error_msg, error, form.errors[error])
        msg = Storage(error = error_msg)

    response.headers["Content-Type"] = "text/html"  # This is what the file-uploader widget expects
    return json.dumps(msg)

# END =========================================================================

