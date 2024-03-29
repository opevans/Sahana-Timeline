# -*- coding: utf-8 -*-

"""
    Custom UI Widgets

    @author: Michael Howden <michael@aidiq.com>
    @author: Fran Boon <fran@aidiq.com>
    @author: Dominic König <dominic@aidiq.com>

    @requires: U{B{I{gluon}} <http://web2py.com>}

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

__all__ = ["S3DateWidget",
           "S3DateTimeWidget",
           #"S3UploadWidget",
           "S3AutocompleteWidget",
           "S3LocationAutocompleteWidget",
           "S3OrganisationAutocompleteWidget",
           "S3PersonAutocompleteWidget",
           "S3SiteAutocompleteWidget",
           "S3LocationSelectorWidget",
           "S3LocationDropdownWidget",
           #"S3CheckboxesWidget",
           "S3MultiSelectWidget",
           "S3ACLWidget",
           "CheckboxesWidgetS3",
           "S3AddPersonWidget",
           "S3AutocompleteOrAddWidget",
           "S3AddObjectWidget",
           "S3SearchAutocompleteWidget",
           "S3TimeIntervalWidget"
           ]

import copy
import datetime

from lxml import etree

from gluon import *
from gluon.storage import Storage
from gluon.sqlhtml import *

from s3utils import *
from s3validators import *

repr_select = lambda l: len(l.name) > 48 and "%s..." % l.name[:44] or l.name

# -----------------------------------------------------------------------------
class S3DateWidget(FormWidget):

    """
        Standard Date widget, but with a modified yearRange to support Birth dates

        @author: Fran Boon (fran@aidiq.com)
    """

    def __init__(self,
                 format = None,
                 past=1440,     # how many months into the past the date can be set to
                 future=1440    # how many months into the future the date can be set to
                ):

        if not format:
            # default: "yy-mm-dd"
            format = current.deployment_settings.get_L10n_date_format().replace("%Y", "yy").replace("%y", "y").replace("%m", "mm").replace("%d", "dd")
        self.format = format
        self.past = past
        self.future = future

    def __call__(self, field, value, **attributes):

        response = current.response

        default = dict(
            _type = "text",
            value = (value != None and str(value)) or "",
            )
        attr = StringWidget._attributes(field, default, **attributes)

        selector = str(field).replace(".", "_")

        response.s3.jquery_ready.append("""
$( '#%s' ).datepicker( 'option', 'minDate', '-%sm' );
$( '#%s' ).datepicker( 'option', 'maxDate', '+%sm' );
$( '#%s' ).datepicker( 'option', 'yearRange', 'c-100:c+100' );
$( '#%s' ).datepicker( 'option', 'dateFormat', '%s' );
""" % (selector,
       self.past,
       selector,
       self.future,
       selector,
       selector,
       self.format))

        return TAG[""](
                        INPUT(**attr),
                        requires = field.requires
                      )

# -----------------------------------------------------------------------------
class S3DateTimeWidget(FormWidget):

    """
        Standard DateTime widget, based on the widget above, but instead of using
        jQuery datepicker we use Anytime.

        @author: Fran Boon (fran@aidiq.com)
    """

    def __init__(self,
                 format = None,
                 past=876000,     # how many hours into the past the date can be set to
                 future=876000    # how many hours into the future the date can be set to
                ):

        if not format:
            # default: "%Y-%m-%d %T"
            format = current.deployment_settings.get_L10n_datetime_format()
        self.format = format
        self.past = past
        self.future = future

    def __call__(self, field, value, **attributes):

        format = str(self.format)
        request = current.request
        response = current.response
        session = current.session
        
        if isinstance(value, datetime.datetime):
            value = value.strftime(format)
        elif value is None:
            value = ""

        default = dict(_type = "text",
                       # Prevent default "datetime" calendar from showing up:
                       _class = "anytime",
                       value = value,
                       old_value = value)

        attr = StringWidget._attributes(field, default, **attributes)

        selector = str(field).replace(".", "_")

        now = request.utcnow
        offset = IS_UTC_OFFSET.get_offset_value(session.s3.utc_offset)
        if offset:
            now = now + datetime.timedelta(seconds=offset)
        timedelta = datetime.timedelta
        earliest = now - timedelta(hours = self.past)
        latest = now + timedelta(hours = self.future)

        earliest = earliest.strftime(format)
        latest = latest.strftime(format)
        
        s3_script_dir = "/%s/static/scripts/S3" % request.application
        if session.s3.debug and \
           "%s/anytime.js" % s3_script_dir not in response.s3.scripts:
            response.s3.scripts.append( "%s/anytime.js" % s3_script_dir )
            response.s3.stylesheets.append( "S3/anytime.css" )
        elif "%s/anytimec.js" % s3_script_dir not in response.s3.scripts:
            response.s3.scripts.append( "%s/anytimec.js" % s3_script_dir )
            response.s3.stylesheets.append( "S3/anytimec.css" )
        
        response.s3.jquery_ready.append("""
$( '#%s' ).AnyTime_picker({
    askSecond: false,
    firstDOW: 1,
    earliest: '%s',
    latest: '%s',
    format: '%s'
});""" % (selector,
          earliest,
          latest,
          format.replace("%M", "%i")))

        return TAG[""](
                        INPUT(**attr),
                        requires = field.requires
                      )


# -----------------------------------------------------------------------------
class S3UploadWidget(UploadWidget):

    """
        Subclassed to not show the delete checkbox when field is mandatory
            - This now been included as standard within Web2Py from r2867
            - Leaving this unused example in the codebase so that we can easily
              amend this if we wish to later

        @author: Fran Boon (fran@aidiq.com)
    """

    @staticmethod
    def widget(field, value, download_url=None, **attributes):
        """
        generates a INPUT file tag.

        Optionally provides an A link to the file, including a checkbox so
        the file can be deleted.
        All is wrapped in a DIV.

        @see: :meth:`FormWidget.widget`
        @param download_url: Optional URL to link to the file (default = None)

        """

        default=dict(
            _type="file",
            )
        attr = UploadWidget._attributes(field, default, **attributes)

        inp = INPUT(**attr)

        if download_url and value:
            url = "%s/%s" % (download_url, value)
            (br, image) = ("", "")
            if UploadWidget.is_image(value):
                br = BR()
                image = IMG(_src = url, _width = UploadWidget.DEFAULT_WIDTH)

            requires = attr["requires"]
            if requires == [] or isinstance(requires, IS_EMPTY_OR):
                inp = DIV(inp, "[",
                          A(UploadWidget.GENERIC_DESCRIPTION, _href = url),
                          "|",
                          INPUT(_type="checkbox",
                                _name=field.name + UploadWidget.ID_DELETE_SUFFIX),
                          UploadWidget.DELETE_FILE,
                          "]", br, image)
            else:
                inp = DIV(inp, "[",
                          A(UploadWidget.GENERIC_DESCRIPTION, _href = url),
                          "]", br, image)
        return inp

# -----------------------------------------------------------------------------
class S3AutocompleteWidget(FormWidget):

    """
        Renders a SELECT as an INPUT field with AJAX Autocomplete

        @author: Fran Boon (fran@aidiq.com)
    """

    def __init__(self,
                 prefix,
                 resourcename,
                 fieldname="name",
                 post_process = "",
                 delay = 450,     # milliseconds
                 min_length = 2): # Increase this for large deployments

        self.prefix = prefix
        self.resourcename = resourcename
        self.fieldname = fieldname
        self.post_process = post_process
        self.delay = delay
        self.min_length = min_length

        # @ToDo: Refreshes all dropdowns as-necessary
        self.post_process = post_process or "" 

    def __call__(self, field, value, **attributes):

        request = current.request
        response = current.response

        default = dict(
            _type = "text",
            value = (value != None and str(value)) or "",
            )
        attr = StringWidget._attributes(field, default, **attributes)

        # Hide the real field
        attr["_class"] = attr["_class"] + " hidden"

        real_input = str(field).replace(".", "_")
        dummy_input = "dummy_%s" % real_input
        fieldname = self.fieldname
        url = URL(c=self.prefix,
                  f=self.resourcename,
                  args="search.json",
                  vars={"filter":"~",
                        "field":fieldname})

        js_autocomplete = "".join(("""
var data = { val:$('#%s').val(), accept:false };
$('#%s').autocomplete({
    source: '%s',
    delay: %d,
    minLength: %d,
    search: function(event, ui) {
        $( '#%s_throbber' ).removeClass('hidden').show();
        return true;
    },
    response: function(event, ui, content) {
        $( '#%s_throbber' ).hide();
        return content;
    },
    focus: function( event, ui ) {
        $( '#%s' ).val( ui.item.%s );
        return false;
    },
    select: function( event, ui ) {
        $( '#%s' ).val( ui.item.%s );
        $( '#%s' ).val( ui.item.id );
        """ % (dummy_input,
               dummy_input,
               url,
               self.delay,
               self.min_length,
               dummy_input,
               dummy_input,
               dummy_input,
               fieldname,
               dummy_input,
               fieldname,
               real_input), self.post_process, """
        data.accept = true;
        return false;
    }
})
.data( 'autocomplete' )._renderItem = function( ul, item ) {
    return $( '<li></li>' )
        .data( 'item.autocomplete', item )
        .append( '<a>' + item.%s + '</a>' )
        .appendTo( ul );
};
$('#%s').blur(function() {
    if (!$('#%s').val()) {
        $('#%s').val('');
        data.accept = true;
    }
    if (!data.accept) {
        $('#%s').val(data.val);
    } else {
        data.val = $('#%s').val();
    }
    data.accept = false;
});""" % (fieldname,
          dummy_input,
          dummy_input,
          real_input,
          dummy_input,
          dummy_input)))

        if value:
            text = str(field.represent(default["value"]))
            if "<" in text:
                # Strip Markup
                try:
                    markup = etree.XML(text)
                    text = markup.xpath(".//text()")
                    if text:
                        text = " ".join(text)
                    else:
                        text = ""
                except etree.XMLSyntaxError:
                    pass
            represent = text
        else:
            represent = ""

        response.s3.jquery_ready.append(js_autocomplete)
        return TAG[""](
                        INPUT(_id=dummy_input,
                              _class="string",
                              _value=represent),
                        IMG(_src="/%s/static/img/ajax-loader.gif" % \
                                 request.application,
                            _height=32, _width=32,
                            _id="%s_throbber" % dummy_input,
                            _class="throbber hidden"),
                        INPUT(**attr),
                        requires = field.requires
                      )


# -----------------------------------------------------------------------------
class S3LocationAutocompleteWidget(FormWidget):

    """
        Renders a gis_location SELECT as an INPUT field with AJAX Autocomplete

        @note: differs from the S3AutocompleteWidget:
            - needs to have deployment_settings passed-in
            - excludes unreliable imported records (Level 'XX')

        Currently used for selecting the region location in gis_config.
        Appropriate when the location has been previously created (as is the
        case for location groups or other specialized locations that need
        the location create form).
        S3LocationSelectorWidget may be more appropriate for specific locations.

        @author: Fran Boon (fran@aidiq.com)
        @todo: .represent for the returned data
        @todo: Refreshes any dropdowns as-necessary (post_process)
    """

    def __init__(self,
                 prefix="gis",
                 resourcename="location",
                 fieldname="name",
                 level="",
                 hidden = False,
                 post_process = "",
                 delay = 450,     # milliseconds
                 min_length = 2): # Increase this for large deployments

        self.deployment_settings = current.deployment_settings
        self.prefix = prefix
        self.resourcename = resourcename
        self.fieldname = fieldname
        self.level = level
        self.hidden = hidden
        self.post_process = post_process
        self.delay = delay
        self.min_length = min_length

    def __call__(self, field, value, **attributes):
        fieldname = self.fieldname
        level = self.level
        if level:
            if isinstance(level, list):
                levels = ""
                counter = 0
                for _level in level:
                    levels += _level
                    if counter < len(level):
                        levels += "|"
                    counter += 1
                url = URL(c=self.prefix,
                          f=self.resourcename,
                          args="search.json",
                          vars={"filter":"~",
                                "field":fieldname,
                                "level":levels})
            else:
                url = URL(c=self.prefix,
                          f=self.resourcename,
                          args="search.json",
                          vars={"filter":"~",
                                "field":fieldname,
                                "level":level})
        else:
            url = URL(c=self.prefix,
                      f=self.resourcename,
                      args="search.json",
                      vars={"filter":"~",
                            "field":fieldname,
                            "exclude_field":"level",
                            "exclude_value":"XX"})

        # Which Levels do we have in our hierarchy & what are their Labels?
        #location_hierarchy = gis.get_location_hierarchy()
        location_hierarchy = self.deployment_settings.gis.location_hierarchy
        try:
            # Ignore the bad bulk-imported data
            del location_hierarchy["XX"]
        except KeyError:
            pass
        # What is the maximum level of hierarchy?
        #max_hierarchy = gis.get_max_hierarchy_level()
        # Is full hierarchy mandatory?
        #strict = gis.get_strict_hierarchy()

        return S3GenericAutocompleteTemplate(
            self.post_process,
            self.delay,
            self.min_length,
            field,
            value,
            attributes,
            transform_value = lambda value: value,
            source = repr(url),
            name_getter = "function (item) { return item.name }",
            id_getter = "function (item) { return item.id }"
        )

# -----------------------------------------------------------------------------
class S3OrganisationAutocompleteWidget(FormWidget):

    """
        Renders an org_organisation SELECT as an INPUT field with AJAX Autocomplete.
        Differs from the S3AutocompleteWidget in that it uses name & acronym fields

        @author: Fran Boon (fran@aidiq.com)

        @ToDo: Add an option to hide the widget completely when using the Org from the Profile
               - i.e. prevent user overrides
    """

    def __init__(self,
                 post_process = "",
                 default_from_profile = False,
                 delay = 450,     # milliseconds
                 min_length = 2): # Increase this for large deployments

        self.post_process = post_process
        self.delay = delay
        self.min_length = min_length
        self.default_from_profile = default_from_profile

    def __call__(self, field, value, **attributes):

        def transform_value(value):
            if not value and self.default_from_profile:
                session = current.session
                if session.auth and session.auth.user:
                    value = session.auth.user.organisation_id
            return value

        return S3GenericAutocompleteTemplate(
            self.post_process,
            self.delay,
            self.min_length,
            field,
            value,
            attributes,
            transform_value = transform_value,
            source = repr(
                URL(c="org", f="organisation",
                      args="search.json",
                      vars={"filter":"~"})
            ),
            name_getter = """function (item) {
    var name = '';
    if (item.name != null) {
        name += item.name;
    }
    if (item.acronym != '') {
        name += ' (' + item.acronym + ')';
    }
    return name;
}""",
            id_getter = "function (item) { return item.id }"
        )

# -----------------------------------------------------------------------------
class S3PersonAutocompleteWidget(FormWidget):

    """
        Renders a pr_person SELECT as an INPUT field with AJAX Autocomplete.
        Differs from the S3AutocompleteWidget in that it uses 3 name fields

        @author: Fran Boon (fran@aidiq.com)

        @ToDo: Migrate to template (initial attempt failed)
    """

    def __init__(self,
                 post_process = "",
                 delay = 450,   # milliseconds
                 min_length=2): # Increase this for large deployments

        self.post_process = post_process
        self.delay = delay
        self.min_length = min_length

    def __call__(self, field, value, **attributes):

        request = current.request
        response = current.response

        default = dict(
            _type = "text",
            value = (value != None and str(value)) or "",
            )
        attr = StringWidget._attributes(field, default, **attributes)

        # Hide the real field
        attr["_class"] = "%s hidden" % attr["_class"]

        real_input = str(field).replace(".", "_")
        dummy_input = "dummy_%s" % real_input
        url = URL(c="pr", f="person",
                  args="search.json",
                  vars={"filter":"~"})

        js_autocomplete = "".join(("""
var data = { val:$('#%s').val(), accept:false };
$('#%s').autocomplete({
    source: '%s',
    delay: %d,
    minLength: %d,
    search: function(event, ui) {
        $( '#%s_throbber' ).removeClass('hidden').show();
        return true;
    },
    response: function(event, ui, content) {
        $( '#%s_throbber' ).hide();
        return content;
    },
    focus: function( event, ui ) {
        var name = '';
        if (ui.item.first_name != null) {
            name += ui.item.first_name;
        }
        if (ui.item.middle_name != null) {
            name += ' ' + ui.item.middle_name;
        }
        if (ui.item.last_name != null) {
            name += ' ' + ui.item.last_name;
        }
        $( '#%s' ).val( name );
        return false;
    },
    select: function( event, ui ) {
        var name = '';
        if (ui.item.first_name != null) {
            name += ui.item.first_name;
        }
        if (ui.item.middle_name != null) {
            name += ' ' + ui.item.middle_name;
        }
        if (ui.item.last_name != null) {
            name += ' ' + ui.item.last_name;
        }
        $( '#%s' ).val( name );
        $( '#%s' ).val( ui.item.id )
                  .change();
        """ % (dummy_input,
               dummy_input,
               url,
               self.delay,
               self.min_length,
               dummy_input,
               dummy_input,
               dummy_input,
               dummy_input,
               real_input), self.post_process, """
        data.accept = true;
        return false;
    }
})
.data( 'autocomplete' )._renderItem = function( ul, item ) {
    var name = '';
    if (item.first_name != null) {
        name += item.first_name;
    }
    if (item.middle_name != null) {
        name += ' ' + item.middle_name;
    }
    if (item.last_name != null) {
        name += ' ' + item.last_name;
    }
    return $( '<li></li>' )
        .data( 'item.autocomplete', item )
        .append( '<a>' + name + '</a>' )
        .appendTo( ul );
};
$('#%s').blur(function() {
    if (!$('#%s').val()) {
        $('#%s').val('')
                .change();
        data.accept = true;
    }
    if (!data.accept) {
        $('#%s').val(data.val);
    } else {
        data.val = $('#%s').val();
    }
    data.accept = false;
});""" % (dummy_input, dummy_input, real_input, dummy_input, dummy_input)))

        if value:
            # Provide the representation for the current/default Value
            text = str(field.represent(default["value"]))
            if "<" in text:
                # Strip Markup
                try:
                    markup = etree.XML(text)
                    text = markup.xpath(".//text()")
                    if text:
                        text = " ".join(text)
                    else:
                        text = ""
                except etree.XMLSyntaxError:
                    pass
            represent = text
        else:
            represent = ""

        response.s3.jquery_ready.append(js_autocomplete)
        return TAG[""](
                        INPUT(_id=dummy_input,
                              _class="string",
                              _value=represent),
                        IMG(_src="/%s/static/img/ajax-loader.gif" % \
                                 request.application,
                            _height=32, _width=32,
                            _id="%s_throbber" % dummy_input,
                            _class="throbber hidden"),
                        INPUT(**attr),
                        requires = field.requires
                      )


# -----------------------------------------------------------------------------
class S3SiteAutocompleteWidget(FormWidget):

    """
        Renders an org_site SELECT as an INPUT field with AJAX Autocomplete.
        Differs from the S3AutocompleteWidget in that it uses name & type fields
        in the represent

        @author: Fran Boon (fran@aidiq.com)
    """

    def __init__(self,
                 post_process = "",
                 delay = 450, # milliseconds
                 min_length = 2):

        self.auth = current.auth
        self.post_process = post_process
        self.delay = delay
        self.min_length = min_length

    def __call__(self, field, value, **attributes):






        request = current.request
        response = current.response
        auth = self.auth

        default = dict(
            _type = "text",
            value = (value != None and str(value)) or "",
            )
        attr = StringWidget._attributes(field, default, **attributes)

        # Hide the real field
        attr["_class"] = "%s hidden" % attr["_class"]

        real_input = str(field).replace(".", "_")
        dummy_input = "dummy_%s" % real_input
        url = URL(c="org", f="site",
                  args="search.json",
                  vars={"filter":"~",
                        "field":"name"})

        # Provide a Lookup Table for Site Types
        cases = ""
        case = -1
        for instance_type in auth.org_site_types.keys():
            case = case + 1
            cases += """
                    case '%s':
                        return '%s';
            """ % (instance_type,
                   auth.org_site_types[instance_type])

        js_autocomplete = "".join(("""
function s3_site_lookup(instance_type) {
    switch (instance_type) {
        %s
    }
}""" % cases, """
var data = { val:$('#%s').val(), accept:false };
$('#%s').autocomplete({
    source: '%s',
    delay: %d,
    minLength: %d,
    search: function(event, ui) {
        $( '#%s_throbber' ).removeClass('hidden').show();
        return true;
    },
    response: function(event, ui, content) {
        $( '#%s_throbber' ).hide();
        return content;
    },
    focus: function( event, ui ) {
        var name = '';
        if (ui.item.name != null) {
            name += ui.item.name;
        }
        if (ui.item.instance_type != '') {
            name += ' (' + s3_site_lookup(ui.item.instance_type) + ')';
        }
        $( '#%s' ).val( name );
        return false;
    },
    select: function( event, ui ) {
        var name = '';
        if (ui.item.name != null) {
            name += ui.item.name;
        }
        if (ui.item.instance_type != '') {
            name += ' (' + s3_site_lookup(ui.item.instance_type) + ')';
        }
        $( '#%s' ).val( name );
        $( '#%s' ).val( ui.item.site_id )
                  .change();
        """ % (dummy_input,
               dummy_input,
               url,
               self.delay,
               self.min_length,
               dummy_input,
               dummy_input,
               dummy_input,
               dummy_input,
               real_input), self.post_process, """
        data.accept = true;
        return false;
    }
})
.data( 'autocomplete' )._renderItem = function( ul, item ) {
    var name = '';
    if (item.name != null) {
        name += item.name;
    }
    if (item.instance_type != '') {
        name += ' (' + s3_site_lookup(item.instance_type) + ')';
    }
    return $( '<li></li>' )
        .data( 'item.autocomplete', item )
        .append( '<a>' + name + '</a>' )
        .appendTo( ul );
};
$('#%s').blur(function() {
    if (!$('#%s').val()) {
        $('#%s').val('')
                .change();
        data.accept = true;
    }
    if (!data.accept) {
        $('#%s').val(data.val);
    } else {
        data.val = $('#%s').val();
    }
    data.accept = false;
});""" % (dummy_input, dummy_input, real_input, dummy_input, dummy_input)))

        if value:
            # Provide the representation for the current/default Value
            text = str(field.represent(default["value"]))
            if "<" in text:
                # Strip Markup
                try:
                    markup = etree.XML(text)
                    text = markup.xpath(".//text()")
                    if text:
                        text = " ".join(text)
                    else:
                        text = ""
                except etree.XMLSyntaxError:
                    pass
            represent = text
        else:
            represent = ""

        response.s3.jquery_ready.append(js_autocomplete)
        return TAG[""](
                        INPUT(_id=dummy_input,
                              _class="string",
                              _value=represent),
                        IMG(_src="/%s/static/img/ajax-loader.gif" % \
                                 request.application,
                            _height=32, _width=32,
                            _id="%s_throbber" % dummy_input,
                            _class="throbber hidden"),
                        INPUT(**attr),
                        requires = field.requires
                      )

# -----------------------------------------------------------------------------
def S3GenericAutocompleteTemplate(
    post_process,
    delay,
    min_length,
    field,
    value,
    attributes,
    transform_value,
    source,
    name_getter,
    id_getter,    
):
    """
        Renders a SELECT as an INPUT field with AJAX Autocomplete
    """
    request = current.request
    response = current.response

    value = transform_value(value)
    
    default = dict(
        _type = "text",
        value = (value != None and str(value)) or "",
        )
    attr = StringWidget._attributes(field, default, **attributes)

    # Hide the real field
    attr["_class"] = attr["_class"] + " hidden"

    real_input = str(field).replace(".", "_")
    dummy_input = "dummy_%s" % real_input
    
    js_autocomplete = "".join((
            """
var data = { val:$('#%(dummy_input)s').val(), accept:false };
var get_name = %(name_getter)s;
var get_id = %(id_getter)s;
$('#%(dummy_input)s').autocomplete({
    source: %(source)s,
    delay: %(delay)d,
    minLength: %(min_length)d,
    search: function(event, ui) {
        $( '#%(dummy_input)s_throbber' ).removeClass('hidden').show();
        return true;
    },
    response: function(event, ui, content) {
        $( '#%(dummy_input)s_throbber' ).hide();
        return content;
    },
    focus: function( event, ui ) {
        $( '#%(dummy_input)s' ).val( get_name(ui.item) );
        return false;
    },
    select: function( event, ui ) {
        var item = ui.item
        $( '#%(dummy_input)s' ).val( get_name(ui.item) );
        $( '#%(real_input)s' ).val( get_id(ui.item) ).change();
        """ % locals(),
        post_process or "",
        """
        data.accept = true;
        return false;
    }
})
.data( 'autocomplete' )._renderItem = function( ul, item ) {
    return $( '<li></li>' )
        .data( 'item.autocomplete', item )
        .append( '<a>' + get_name(item) + '</a>' )
        .appendTo( ul );
};
$('#%(dummy_input)s').blur(function() {
    if (!$('#%(dummy_input)s').val()) {
        $('#%(real_input)s').val('').change();
        data.accept = true;
    }
    if (!data.accept) {
        $('#%(dummy_input)s').val(data.val);
    } else {
        data.val = $('#%(dummy_input)s').val();
    }
    data.accept = false;
});""" % locals()))

    if value:
        # Provide the representation for the current/default Value
        text = str(field.represent(default["value"]))
        if "<" in text:
            # Strip Markup
            try:
                markup = etree.XML(text)
                text = markup.xpath(".//text()")
                if text:
                    text = " ".join(text)
                else:
                    text = ""
            except etree.XMLSyntaxError:
                pass
        represent = text
    else:
        represent = ""

    response.s3.jquery_ready.append(js_autocomplete)
    return TAG[""](
                    INPUT(_id=dummy_input,
                          _class="string",
                          _value=represent),
                    IMG(_src="/%s/static/img/ajax-loader.gif" % \
                             request.application,
                        _height=32, _width=32,
                        _id="%s_throbber" % dummy_input,
                        _class="throbber hidden"),
                    INPUT(**attr),
                    requires = field.requires
                  )
                      

# -----------------------------------------------------------------------------
class S3Autocompleter(object):
    """ Unused? """
    def __init__(self,
                 prefix,
                 resourcename,
                 fieldname="name"
    ):
        self.prefix = prefix
        self.resourcename = resourcename
        self.fieldname = fieldname

    def source(self):
        return URL(c=self.prefix, f=self.resourcename,
                   args="search.json",
                   vars={"filter":"~",
                         "field":self.fieldname})

    def name_getter(self):
        return "function (item) { return item.%s }" % self.fieldname

    def id_getter(self):
        return "function (item) { return item.id }"

# -----------------------------------------------------------------------------
class S3LocationDropdownWidget(FormWidget):
    """
        Renders a dropdown for an Lx level of location hierarchy

        For LA this is used for States
        For Trunk this could be useful for Countries
    """

    def __init__(self, level="L0", default=None, empty=False):
        """ Set Defaults """
        self.level = level
        self.default = default
        self.empty = empty

    def __call__(self, field, value, **attributes):

        level = self.level
        default = self.default
        empty = self.empty

        db = current.db
        table = db.gis_location
        query = (table.level == level)
        locations = db(query).select(table.name,
                                     table.id,
                                     cache = current.gis.cache)
        opts = []
        for location in locations:
            opts.append(OPTION(location.name, _value=location.id))
            if not value and default and location.name == default:
                value = location.id
        locations = locations.as_dict()
        attr_dropdown = OptionsWidget._attributes(field,
                                                  dict(_type = "int",
                                                       value = value))
        requires = IS_IN_SET(locations)
        if empty:
            requires = IS_NULL_OR(requires)
        attr_dropdown["requires"] = requires

        attr_dropdown["represent"] = \
            lambda id: locations["id"]["name"] or UNKNOWN_OPT

        return TAG[""](
                        SELECT(*opts, **attr_dropdown),
                        requires=field.requires
                      )

# -----------------------------------------------------------------------------
class S3LocationSelectorWidget(FormWidget):

    """
        Renders a gis_location SELECT to allow inline display/editing of linked fields.

        Designed for use for Resources which require a Specific Location, such as Sites, Persons, Assets, Incidents, etc
        Not currently suitable for Resources which require a Hierarchical Location, such as Projects, Assessments, Plans, etc

        It uses s3.locationselector.widget.js to do all client-side functionality.
        It requires the IS_LOCATION_SELECTOR() validator to process Location details upon form submission.

        Create form
            Active Tab: 'Create New Location'
                Country Dropdown (to set the Number & Labels of Hierarchy)
                Building Name (deployment_setting to hide)
                Street Address (Line1/Line2?)
                    @ToDo: Trigger a geocoder lookup onblur
                Postcode
                @ToDo: Mode Strict:
                    Lx as dropdowns. Default label is 'Select previous to populate this dropdown' (Fixme!)
                Mode not Strict (default):
                    L2-L5 as Autocompletes which create missing locations automatically
                    @ToDo: L1 as Dropdown? (Have a gis_config setting to inform whether this is populated for a given L0)
                Map:
                    @ToDo: Inline or Popup? (Deployment Option?)
                    Set Map Viewport to default on best currently selected Hierarchy
                        @ToDo: L1+
                Lat Lon
            Inactive Tab: 'Select Existing Location'
                Needs 2 modes:
                    Specific Locations only - for Sites/Incidents
                    @ToDo: Hierarchies ok (can specify which) - for Projects/Documents
                @ToDo: Hierarchical Filters above the Search Box
                    Search is filtered to values shown
                    Filters default to any hierarchy selected on the Create tab?
                Button to explicitly say 'Select this Location' which sets all the fields (inc hidden ID) & the UUID var
                    Tabs then change to View/Edit

        Update form
            Update form has uuid set server-side & hence S3.gis.uuid set client-side
            Assume location is shared by other resources
                Active Tab: 'View Location Details' (Fields are read-only)
                Inactive Tab: 'Edit Location Details' (Fields are writable)
                @ToDo: Inactive Tab: 'Move Location': Defaults to Searching for an Existing Location, with a button to 'Create New Location'

        @author: Fran Boon (fran@aidiq.com)

        @see: http://eden.sahanafoundation.org/wiki/BluePrintGISLocationSelector
    """

    def __init__(self):
        pass

    def __call__(self, field, value, **attributes):

        db = current.db
        gis = current.gis
        cache = gis.cache

        auth = current.auth
        deployment_settings = current.deployment_settings
        request = current.request
        response = current.response
        manager = current.manager
        T = current.T
        locations = db.gis_location

        # Main Input
        defaults = dict(_type = "text",
                        value = (value != None and str(value)) or "")
        attr = StringWidget._attributes(field, defaults, **attributes)
        # Hide the real field
        attr["_class"] = "hidden"

        # Is this a site?
        tablename = field.tablename
        if tablename in auth.org_site_types:
            site = tablename
        else:
            site = ""

        # Read Options
        config = gis.get_config()
        default_L0 = Storage()
        country_snippet = ""
        if value:
            default_L0.id = gis.get_parent_country(value)
        elif config.default_location_id:
            # Populate defaults with IDs & Names of ancestors at each level
            gis.get_parent_per_level(defaults,
                                     config.default_location_id,
                                     feature=None,
                                     ids=True,
                                     names=True)
            query = (locations.id == config.default_location_id)
            default_location = db(query).select(locations.level,
                                                locations.name).first()
            if default_location.level:
                # Add this one to the defaults too
                defaults[default_location.level] = Storage(name = default_location.name,
                                                           id = config.default_location_id)
            if "L0" in defaults:
                default_L0 = defaults["L0"]
            if default_L0:
                country_snippet = "S3.gis.country = '%s';\n" % \
                    gis.get_default_country(key_type="code")

        # Full list of countries
        countries = gis.get_countries()
        # Should we use a Map-based selector?
        map_selector = deployment_settings.get_gis_map_selector()
        if map_selector:
            no_map = ""
        else:
            no_map = "S3.gis.no_map = true;\n"
        # Should we display LatLon boxes?
        latlon_selector = deployment_settings.get_gis_latlon_selector()
        # Navigate Away Confirm?
        if deployment_settings.get_ui_navigate_away_confirm():
            navigate_away_confirm = """
S3.navigate_away_confirm = true;"""
        else:
            navigate_away_confirm = ""

        # Which tab should the widget open to by default?
        # @ToDo: Act on this server-side instead of client-side
        if response.s3.gis.tab:
            tab = """
S3.gis.tab = '%s';""" % response.s3.gis.tab
        else:
            # Default to Create
            tab = ""

        # Which Levels do we have in our hierarchy & what are their initial Labels?
        # If we have a default country or one from the value then we can lookup
        # the labels we should use for that location
        config_L0 = None
        if default_L0:
            query = (db.gis_config.region_location_id == default_L0.id)
            config_L0 = db(query).select(db.gis_config.id,
                                         limitby=(0, 1),
                                         cache=cache).first()
            if config_L0:
                gis.set_temporary_config(config_L0.id)
        location_hierarchy = gis.get_location_hierarchy()
        # This is all levels to start, but L0 will be dropped later.
        levels = gis.allowed_hierarchy_level_keys
        if config_L0:
            gis.restore_config()

        map_popup = ""
        if value:
            # Read current record
            if auth.s3_has_permission("update", locations, record_id=value):
                # Update mode
                # - we assume this location could be shared by other resources
                create = "hidden"   # Hide sections which are meant for create forms
                update = ""
                query = (locations.id == value)
                this_location = db(query).select(locations.uuid,
                                                 locations.name,
                                                 locations.level,
                                                 locations.lat,
                                                 locations.lon,
                                                 locations.addr_street,
                                                 locations.addr_postcode,
                                                 locations.parent,
                                                 locations.path,
                                                 limitby=(0, 1)).first()
                if this_location:
                    uid = this_location.uuid
                    level = this_location.level
                    defaults[level] = Storage()
                    defaults[level].id = value
                    lat = this_location.lat
                    lon = this_location.lon
                    addr_street = this_location.addr_street or ""
                    #addr_street_encoded = ""
                    #if addr_street:
                    #    addr_street_encoded = addr_street.replace("\r\n",
                    #                                              "%0d").replace("\r",
                    #                                                             "%0d").replace("\n",
                    #                                                                            "%0d")
                    postcode = this_location.addr_postcode
                    parent = this_location.parent
                    path = this_location.path

                    # Populate defaults with IDs & Names of ancestors at each level
                    gis.get_parent_per_level(defaults,
                                             value,
                                             feature=this_location,
                                             ids=True,
                                             names=True)
                    # If we have a non-specific location then not all keys will be populated.
                    # Populate these now:
                    for l in levels:
                        try:
                            defaults[l]
                        except:
                            defaults[l] = None

                    if level and not level == "XX":
                        # If within the locations hierarchy then don't populate the visible name box
                        represent = ""
                    else:
                        represent = this_location.name

                    if map_selector:
                        # Load the Models
                        manager.load("gis_layer_openstreetmap")
                        zoom = config.zoom
                        if lat is None or lon is None:
                            map_lat = config.lat
                            map_lon = config.lon
                        else:
                            map_lat = lat
                            map_lon = lon

                        query = (locations.id == value)
                        row = db(query).select(locations.lat,
                                               locations.lon,
                                               limitby=(0, 1)).first()
                        if row:
                            feature = {"lat"  : row.lat,
                                       "lon"  : row.lon }
                            features = [feature]
                        else:
                            features = []
                        map_popup = gis.show_map(
                                                 lat = map_lat,
                                                 lon = map_lon,
                                                 # Same as a single zoom on a cluster
                                                 zoom = zoom + 2,
                                                 features = features,
                                                 add_feature = True,
                                                 #add_feature_active = True,
                                                 toolbar = True,
                                                 collapsed = True,
                                                 search = True,
                                                 window = True,
                                                 window_hide = True
                                                )
                else:
                    # Bad location_id
                    response.error = T("Invalid Location!")
                    value = None

            elif auth.s3_has_permission("read", locations, record_id=value):
                # Read mode
                # @ToDo
                return ""
            else:
                # No Permission to read location, so don't render a row
                return ""

        if not value:
            # No default value
            # Check that we're allowed to create records
            if auth.s3_has_permission("update", locations):
                # Create mode
                create = ""
                update = "hidden"   # Hide sections which are meant for update forms
                uuid = ""
                represent = ""
                level = None
                lat = None
                lon = None
                addr_street = ""
                #addr_street_encoded = ""
                postcode = ""
                if map_selector:
                    # Load the Models
                    manager.load("gis_layer_openstreetmap")
                    map_popup = gis.show_map(
                                             add_feature = True,
                                             add_feature_active = True,
                                             toolbar = True,
                                             collapsed = True,
                                             search = True,
                                             window = True,
                                             window_hide = True
                                            )
            else:
                # No Permission to create a location, so don't render a row
                return ""

        # JS snippets of config
        # (we only include items with data)
        #if represent:
        #    s3_gis_name = "S3.gis.name = '%s';" % represent
        #else:
        #    s3_gis_name = ""
        #if addr_street_encoded:
        #    s3_gis_address = """
#S3.gis.addr_street = '%s';""" % addr_street_encoded
        #else:
        #    s3_gis_address = ""
        #if postcode:
        #    s3_gis_postcode = """
#S3.gis.postcode = '%s';""" % postcode
        #else:
        #    s3_gis_postcode = ""
        #if lat is not None:
        #    s3_gis_lat_lon = """
#S3.gis.lat = %f;
#S3.gis.lon = %f;""" % (lat, lon)
        #else:
        #
        s3_gis_lat_lon = ""

        # Components to inject into Form
        divider = TR(TD(_class="subheading"), TD(),
                     _class="box_bottom")
        expand_button = DIV(_id="gis_location_expand", _class="minus")
        label_row = TR(TD(B("%s:" % field.label), expand_button), TD(),
                       _id="gis_location_label_row",
                       _class="box_top")

        # Tabs to select between the modes
        # @ToDo: Move Location tab
        view_button = A(T("View Location Details"),
                        _style="cursor:pointer; cursor:hand",
                        _id="gis_location_view-btn")

        edit_button = A(T("Edit Location Details"),
                        _style="cursor:pointer; cursor:hand",
                        _id="gis_location_edit-btn")

        add_button = A(T("Create New Location"),
                       _style="cursor:pointer; cursor:hand",
                       _id="gis_location_add-btn")

        search_button = A(T("Select Existing Location"),
                          _style="cursor:pointer; cursor:hand",
                          _id="gis_location_search-btn")

        tabs = DIV(SPAN(add_button, _id="gis_loc_add_tab",
                        _class="tab_here %s" % create),
                   SPAN(search_button, _id="gis_loc_search_tab",
                        _class="tab_last %s" % create),
                   SPAN(view_button, _id="gis_loc_view_tab",
                        _class="tab_here %s" % update),
                   SPAN(edit_button, _id="gis_loc_edit_tab",
                        _class="tab_last %s" % update),
                   _class="tabs")

        tab_rows = TR(TD(tabs), TD(),
                      _id="gis_location_tabs_row",
                      _class="locselect box_middle")

        # L0 selector
        SELECT_LOCATION = T("Select a location")
        level = "L0"
        L0_rows = ""
        #if len(countries) == 1:
        #    # Hard-coded country
        #    (cid, country) = countries.items()[0]
        #    L0_rows = INPUT(value = cid,
        #                    _id="gis_location_%s" % level,
        #                    _name="gis_location_%s" % level,
        #                    _class="hidden box_middle")
        #else:
        if default_L0:
            attr_dropdown = OptionsWidget._attributes(field,
                                                      dict(_type = "int",
                                                           value = default_L0.id),
                                                      **attributes)
        else:
            attr_dropdown = OptionsWidget._attributes(field,
                                                      dict(_type = "int",
                                                           value = ""),
                                                      **attributes)
        attr_dropdown["requires"] = \
            IS_NULL_OR(IS_IN_SET(countries,
                                 zero = SELECT_LOCATION))
        attr_dropdown["represent"] = \
            lambda id: gis.get_country(id) or UNKNOWN_OPT
        opts = [OPTION(SELECT_LOCATION, _value="")]
        if countries:
            for (id, name) in countries.iteritems():
                opts.append(OPTION(name, _value=id))
        attr_dropdown["_id"] = "gis_location_%s" % level
        ## Old: Need to blank the name to prevent it from appearing in form.vars & requiring validation
        #attr_dropdown["_name"] = ""
        attr_dropdown["_name"] = "gis_location_%s" % level
        if value:
            # Update form => read-only
            attr_dropdown["_disabled"] = "disabled"
            try:
                attr_dropdown["value"] = defaults[level].id
            except:
                pass
        widget = SELECT(*opts, **attr_dropdown)
        label = LABEL("%s:" % location_hierarchy[level])
        L0_rows = DIV(TR(TD(label), TD(),
                         _class="locselect box_middle",
                         _id="gis_location_%s_label__row" % level),
                      TR(TD(widget), TD(),
                         _class="locselect box_middle",
                         _id="gis_location_%s__row" % level))
        row = TR(INPUT(_id="gis_location_%s_search" % level,
                       _disabled="disabled"), TD(),
                 _class="hidden locselect box_middle",
                 _id="gis_location_%s_search__row" % level)
        L0_rows.append(row)

        NAME_LABEL = T("Building Name")
        STREET_LABEL = T("Street Address")
        POSTCODE_LABEL = deployment_settings.get_ui_label_postcode()
        LAT_LABEL = T("Latitude")
        LON_LABEL = T("Longitude")
        AUTOCOMPLETE_HELP = T("Enter some characters to bring up a list of possible matches")
        NEW_HELP = T("If not found, you can have a new location created.")
        def ac_help_widget(level):
            try:
                label = location_hierarchy[level]
            except:
                label = level
            return DIV( _class="tooltip",
                        _title="%s|%s|%s" % (label, AUTOCOMPLETE_HELP, NEW_HELP))

        hidden = ""
        throbber = "/%s/static/img/ajax-loader.gif" % request.application
        Lx_rows = DIV()
        # We added the L0 selector as a special case above.
        try:
            levels.remove("L0")
        except:
            pass
        if value:
            # Display Read-only Fields
            name_widget = INPUT(value=represent,
                                _id="gis_location_name",
                                _name="gis_location_name",
                                _disabled="disabled")
            street_widget = TEXTAREA(value=addr_street,
                                     _id="gis_location_street",
                                     _name="gis_location_street",
                                     _disabled="disabled")
            postcode_widget = INPUT(value=postcode,
                                    _id="gis_location_postcode",
                                    _name="gis_location_postcode",
                                    _disabled="disabled")
            lat_widget = INPUT(value=lat,
                               _id="gis_location_lat",
                               _name="gis_location_lat",
                               _disabled="disabled")
            lon_widget = INPUT(value=lon,
                               _id="gis_location_lon",
                               _name="gis_location_lon",
                               _disabled="disabled")
            for level in levels:
                if level not in location_hierarchy:
                    # Skip levels not in hierarchy
                    continue
                if defaults[level]:
                    id = defaults[level].id
                    name = defaults[level].name
                else:
                    # Hide empty levels
                    hidden = "hidden"
                    id = ""
                    name = ""
                try:
                    label = LABEL("%s:" % location_hierarchy[level])
                except:
                    label = LABEL("%s:" % level)
                row = TR(TD(label), TD(),
                         _id="gis_location_%s_label__row" % level,
                         _class="%s box_middle" % hidden)
                Lx_rows.append(row)
                widget = DIV(INPUT(value=id,
                                   _id="gis_location_%s" % level,
                                   _name="gis_location_%s" % level,
                                   _class="hidden"),
                             INPUT(value=name,
                                   _id="gis_location_%s_ac" % level,
                                   _disabled="disabled"),
                             IMG(_src=throbber,
                                 _height=32, _width=32,
                                 _id="gis_location_%s_throbber" % level,
                                 _class="throbber hidden"))
                row = TR(TD(widget), TD(),
                         _id="gis_location_%s__row" % level,
                         _class="%s locselect box_middle" % hidden)
                Lx_rows.append(row)

        else:
            name_widget = INPUT(_id="gis_location_name",
                                _name="gis_location_name")
            street_widget = TEXTAREA(_id="gis_location_street",
                                     _name="gis_location_street")
            postcode_widget = INPUT(_id="gis_location_postcode",
                                    _name="gis_location_postcode")
            lat_widget = INPUT(_id="gis_location_lat",
                               _name="gis_location_lat")
            lon_widget = INPUT(_id="gis_location_lon",
                               _name="gis_location_lon")
            for level in levels:
                hidden = ""
                if level not in location_hierarchy:
                    # Hide unused levels
                    # (these can then be enabled for other regions)
                    hidden = "hidden"
                try:
                    label = LABEL("%s:" % location_hierarchy[level])
                except:
                    label = LABEL("%s:" % level)
                row = TR(TD(label), TD(),
                         _class="%s locselect box_middle" % hidden,
                         _id="gis_location_%s_label__row" % level)
                Lx_rows.append(row)
                if level in defaults and defaults[level]:
                    default = defaults[level]
                    default_id = default.id
                    default_name = default.name
                else:
                    default_id = ""
                    default_name = ""
                widget = DIV(INPUT(value=default_id,
                                   _id="gis_location_%s" % level,
                                   _name="gis_location_%s" % level,
                                   _class="hidden"),
                                INPUT(value=default_name,
                                      _id="gis_location_%s_ac" % level,
                                      _class="%s" % hidden),
                                IMG(_src=throbber,
                                    _height=32, _width=32,
                                    _id="gis_location_%s_throbber" % level,
                                    _class="throbber hidden"))
                row = TR(TD(widget),
                         TD(ac_help_widget(level)),
                         _class="%s locselect box_middle" % hidden,
                         _id="gis_location_%s__row" % level)
                Lx_rows.append(row)
                row = TR(INPUT(_id="gis_location_%s_search" % level,
                               _disabled="disabled"), TD(),
                         _class="hidden locselect box_middle",
                         _id="gis_location_%s_search__row" % level)
                Lx_rows.append(row)

        if deployment_settings.get_gis_building_name():
            hidden = ""
            if value and not represent:
                hidden = "hidden"
            name_rows = DIV(TR(LABEL("%s:" % NAME_LABEL), TD(),
                               _id="gis_location_name_label__row",
                               _class="%s locselect box_middle" % hidden),
                            TR(name_widget, TD(),
                               _id="gis_location_name__row",
                               _class="%s locselect box_middle" % hidden),
                            TR(INPUT(_id="gis_location_name_search",
                                     _disabled="disabled"), TD(),
                               _id="gis_location_name_search__row",
                               _class="hidden locselect box_middle"))
        else:
            name_rows = ""

        hidden = ""
        if value and not addr_street:
            hidden = "hidden"
        street_rows = DIV(TR(LABEL("%s:" % STREET_LABEL), TD(),
                             _id="gis_location_street_label__row",
                             _class="%s locselect box_middle" % hidden),
                          TR(street_widget, TD(),
                             _id="gis_location_street__row",
                             _class="%s locselect box_middle" % hidden),
                          TR(INPUT(_id="gis_location_street_search",
                                   _disabled="disabled"), TD(),
                             _id="gis_location_street_search__row",
                             _class="hidden locselect box_middle"))
        if config.geocoder:
            geocoder = """
S3.gis.geocoder = true;"""
        else:
            geocoder = ""

        hidden = ""
        if value and not postcode:
            hidden = "hidden"
        postcode_rows = DIV(TR(LABEL("%s:" % POSTCODE_LABEL), TD(),
                               _id="gis_location_postcode_label__row",
                               _class="%s locselect box_middle" % hidden),
                            TR(postcode_widget, TD(),
                               _id="gis_location_postcode__row",
                               _class="%s locselect box_middle" % hidden),
                            TR(INPUT(_id="gis_location_postcode_search",
                                     _disabled="disabled"), TD(),
                               _id="gis_location_postcode_search__row",
                               _class="hidden locselect box_middle"))

        hidden = ""
        no_latlon = ""
        if not latlon_selector:
            hidden = "hidden"
            no_latlon = "S3.gis.no_latlon = true;\n"
        elif value and lat is None:
            hidden = "hidden"
        latlon_help = locations.lat.comment
        converter_button = locations.lon.comment
        converter_button = ""
        latlon_rows = DIV(TR(LABEL("%s:" % LAT_LABEL), TD(),
                               _id="gis_location_lat_label__row",
                               _class="%s locselect box_middle" % hidden),
                          TR(TD(lat_widget), TD(latlon_help),
                               _id="gis_location_lat__row",
                               _class="%s locselect box_middle" % hidden),
                          TR(INPUT(_id="gis_location_lat_search",
                                   _disabled="disabled"), TD(),
                             _id="gis_location_lat_search__row",
                             _class="hidden locselect box_middle"),
                          TR(LABEL("%s:" % LON_LABEL), TD(),
                               _id="gis_location_lon_label__row",
                               _class="%s locselect box_middle" % hidden),
                          TR(TD(lon_widget), TD(converter_button),
                               _id="gis_location_lon__row",
                               _class="%s locselect box_middle" % hidden),
                          TR(INPUT(_id="gis_location_lon_search",
                                   _disabled="disabled"), TD(),
                             _id="gis_location_lon_search__row",
                             _class="hidden locselect box_middle"))

        # Map Selector
        PLACE_ON_MAP = T("Place on Map")
        VIEW_ON_MAP = T("View on Map")
        if map_selector:
            if value:
                map_button = A(VIEW_ON_MAP,
                               _style="cursor:pointer; cursor:hand",
                               _id="gis_location_map-btn",
                               _class="action-btn")
            else:
                map_button = A(PLACE_ON_MAP,
                               _style="cursor:pointer; cursor:hand",
                               _id="gis_location_map-btn",
                               _class="action-btn")
            map_button_row = TR(map_button, TD(),
                                _id="gis_location_map_button_row",
                                _class="locselect box_middle")
        else:
            map_button_row = ""

        # Search
        widget = DIV(INPUT(_id="gis_location_search_ac"),
                           IMG(_src=throbber,
                               _height=32, _width=32,
                               _id="gis_location_search_throbber",
                               _class="throbber hidden"),
                           _id="gis_location_search_div")

        label = LABEL("%s:" % AUTOCOMPLETE_HELP)

        select_button = A(T("Select This Location"),
                          _style="cursor:pointer; cursor:hand",
                          _id="gis_location_search_select-btn",
                          _class="hidden action-btn")

        search_rows = DIV(TR(label, TD(),
                             _id="gis_location_search_label__row",
                             _class="hidden locselect box_middle"),
                          TR(TD(widget),
                             TD(select_button),
                             _id="gis_location_search__row",
                             _class="hidden locselect box_middle"))
        # @ToDo: Hierarchical Filter
        Lx_search_rows = ""

        # Error Messages
        NAME_REQUIRED = T("Name field is required!")
        COUNTRY_REQUIRED = T("Country is required!")

        # Settings to be read by static/scripts/S3/s3.locationselector.widget.js
#S3.gis.uuid = '%s';
#%s%s%s%s
        js_location_selector = """
%s%s%s%s%s%s
S3.gis.location_id = '%s';
S3.gis.site = '%s';
S3.i18n.gis_place_on_map = '%s';
S3.i18n.gis_view_on_map = '%s';
S3.i18n.gis_name_required = '%s';
S3.i18n.gis_country_required = '%s';""" % (
                                            #uuid,
                                            #s3_gis_name,
                                            #s3_gis_address,
                                            #s3_gis_postcode,
                                            #s3_gis_lat_lon,
                                            country_snippet,
                                            geocoder,
                                            navigate_away_confirm,
                                            no_latlon,
                                            no_map,
                                            tab,
                                            attr["_id"],    # Name of the real location field
                                            site,
                                            PLACE_ON_MAP,
                                            VIEW_ON_MAP,
                                            NAME_REQUIRED,
                                            COUNTRY_REQUIRED
                                        )

        # The overall layout of the components
        return TAG[""](
                        TR(INPUT(**attr)),  # Real input, which is hidden
                        label_row,
                        tab_rows,
                        Lx_search_rows,
                        search_rows,
                        L0_rows,
                        name_rows,
                        street_rows,
                        postcode_rows,
                        Lx_rows,
                        map_button_row,
                        latlon_rows,
                        divider,
                        TR(map_popup,  TD(), _class="box_middle"),
                        SCRIPT(js_location_selector),
                        requires=field.requires
                      )


# -----------------------------------------------------------------------------
class S3CheckboxesWidget(OptionsWidget):

    """
        Generates a TABLE tag with <num_column> columns of INPUT
        checkboxes (multiple allowed)

        @author: Michael Howden (michael@aidiq.com)

        help_lookup_table_name_field will display tooltip help

        :param db: int -
        :param lookup_table_name: int -
        :param lookup_field_name: int -
        :param multple: int -

        :param options: list - optional -
        value,text pairs for the Checkboxs -
        If options = None,  use options from self.requires.options().
        This argument is useful for displaying a sub-set of the self.requires.options()

        :param num_column: int -

        :param help_lookup_field_name: string - optional -

        :param help_footer: string -

        Currently unused
    """

    def __init__(self,
                 db = None,
                 lookup_table_name = None,
                 lookup_field_name = None,
                 multiple = False,
                 options = None,
                 num_column = 1,
                 help_lookup_field_name = None,
                 help_footer = None
                 ):

        current.db = db
        self.lookup_table_name = lookup_table_name
        self.lookup_field_name =  lookup_field_name
        self.multiple = multiple

        self.num_column = num_column

        self.help_lookup_field_name = help_lookup_field_name
        self.help_footer = help_footer

        if db and lookup_table_name and lookup_field_name:
            self.requires = IS_NULL_OR(IS_IN_DB(db,
                                   db[lookup_table_name].id,
                                   "%(" + lookup_field_name + ")s",
                                   multiple = multiple))

        if options:
            self.options = options
        else:
            if hasattr(self.requires, "options"):
                self.options = self.requires.options()
            else:
                raise SyntaxError, "widget cannot determine options of %s" % field


    def widget( self,
                field,
                value = None
                ):
        if current.db:
            db = current.db
        else:
            db = field._db

        values = s3_split_multi_value(value)

        attr = OptionsWidget._attributes(field, {})

        num_row  = len(self.options)/self.num_column
        # Ensure division  rounds up
        if len(self.options) % self.num_column > 0:
             num_row = num_row +1

        table = TABLE(_id = str(field).replace(".", "_"))

        for i in range(0,num_row):
            table_row = TR()
            for j in range(0, self.num_column):
                # Check that the index is still within self.options
                index = num_row*j + i
                if index < len(self.options):
                    input_options = {}
                    input_options = dict(requires = attr.get("requires", None),
                                         _value = str(self.options[index][0]),
                                         value = values,
                                         _type = "checkbox",
                                         _name = field.name,
                                         hideerror = True
                                        )
                    tip_attr = {}
                    help_text = ""
                    if self.help_lookup_field_name:
                        help_text = str(P(s3_get_db_field_value(tablename = self.lookup_table_name,
                                                                fieldname = self.help_lookup_field_name,
                                                                look_up_value = self.options[index][0],
                                                                look_up_field = "id")))
                    if self.help_footer:
                        help_text = help_text + str(self.help_footer)
                    if help_text:
                        tip_attr = dict(_class = "s3_checkbox_label",
                                        #_title = self.options[index][1] + "|" + help_text
                                        _rel =  help_text
                                        )

                    #table_row.append(TD(A(self.options[index][1],**option_attr )))
                    table_row.append(TD(INPUT(**input_options),
                                        SPAN(self.options[index][1], **tip_attr)
                                        )
                                    )
            table.append (table_row)
        if self.multiple:
            table.append(TR(I("(Multiple selections allowed)")))
        return table


    def represent(self,
                  value):
        list = [s3_get_db_field_value(tablename = self.lookup_table_name,
                                      fieldname = self.lookup_field_name,
                                      look_up_value = id,
                                      look_up_field = "id")
                   for id in s3_split_multi_value(value) if id]
        if list and not None in list:
            return ", ".join(list)
        else:
            return None


# -----------------------------------------------------------------------------
class S3MultiSelectWidget(MultipleOptionsWidget):

    """
        Standard MultipleOptionsWidget, but using the jQuery UI:
        http://www.quasipartikel.at/multiselect/
        static/scripts/S3/ui.multiselect.js

        @author: Fran Boon (fran@aidiq.com)
    """

    def __init__(self):
        pass

    def __call__(self, field, value, **attributes):

        response = current.response
        T = current.T

        selector = str(field).replace(".", "_")

        response.s3.js_global.append("""
S3.i18n.addAll = '%s';
S3.i18n.removeAll = '%s';
S3.i18n.itemsCount = '%s';
S3.i18n.search = '%s';
""" % (T("Add all"),
       T("Remove all"),
       T("items selected"),
       T("search")))

        response.s3.jquery_ready.append("""
$( '#%s' ).removeClass('list');
$( '#%s' ).addClass('multiselect');
$( '#%s' ).multiselect({
        dividerLocation: 0.5,
        sortable: false
    });
""" % (selector,
       selector,
       selector))

        return TAG[""](
                        MultipleOptionsWidget.widget(field, value, **attributes),
                        requires = field.requires
                      )


# -----------------------------------------------------------------------------
class S3ACLWidget(CheckboxesWidget):

    """
        Widget class for ACLs

        @author: Dominic König <dominic@aidiq.com>

        @todo: add option dependency logic (JS)
        @todo: configurable vertical/horizontal alignment
    """

    @staticmethod
    def widget(field, value, **attributes):

        requires = field.requires
        if not isinstance(requires, (list, tuple)):
            requires = [requires]
        if requires:
            if hasattr(requires[0], "options"):
                options = requires[0].options()
                values = []
                for k in options:
                    if isinstance(k, (list, tuple)):
                        k = k[0]
                    try:
                        flag = int(k)
                        if flag == 0:
                            if value == 0:
                                values.append(k)
                                break
                            else:
                                continue
                        elif value and value & flag == flag:
                            values.append(k)
                    except ValueError:
                        pass
                value = values

        #return CheckboxesWidget.widget(field, value, **attributes)

        attr = OptionsWidget._attributes(field, {}, **attributes)

        options = [(k, v) for k, v in options if k != ""]
        opts = []
        cols = attributes.get("cols", 1)
        totals = len(options)
        mods = totals%cols
        rows = totals/cols
        if mods:
            rows += 1

        for r_index in range(rows):
            tds = []
            for k, v in options[r_index*cols:(r_index+1)*cols]:
                tds.append(TD(INPUT(_type="checkbox",
                                    _name=attr.get("_name", field.name),
                                    requires=attr.get("requires", None),
                                    hideerror=True, _value=k,
                                    value=(k in value)), v))
            opts.append(TR(tds))

        if opts:
            opts[-1][0][0]["hideerror"] = False
        return TABLE(*opts, **attr)

        # was values = re.compile("[\w\-:]+").findall(str(value))
        #values = not isinstance(value,(list,tuple)) and [value] or value


        #requires = field.requires
        #if not isinstance(requires, (list, tuple)):
            #requires = [requires]
        #if requires:
            #if hasattr(requires[0], "options"):
                #options = requires[0].options()
            #else:
                #raise SyntaxError, "widget cannot determine options of %s" \
                    #% field

# -----------------------------------------------------------------------------
class CheckboxesWidgetS3(OptionsWidget):
    """
        S3 version of gluon.sqlhtml.CheckboxesWidget:
        - supports also integer-type keys in option sets

        Used in s3aaa
    """

    @staticmethod
    def widget(field, value, **attributes):
        """
        generates a TABLE tag, including INPUT checkboxes (multiple allowed)

        see also: :meth:`FormWidget.widget`
        """

        # was values = re.compile("[\w\-:]+").findall(str(value))
        values = not isinstance(value,(list,tuple)) and [value] or value
        values = [str(v) for v in values]

        attr = OptionsWidget._attributes(field, {}, **attributes)

        requires = field.requires
        if not isinstance(requires, (list, tuple)):
            requires = [requires]
        if requires:
            if hasattr(requires[0], "options"):
                options = requires[0].options()
            else:
                raise SyntaxError, "widget cannot determine options of %s" \
                    % field

        options = [(k, v) for k, v in options if k != ""]
        opts = []
        cols = attributes.get("cols", 1)
        totals = len(options)
        mods = totals % cols
        rows = totals / cols
        if mods:
            rows += 1

        for r_index in range(rows):
            tds = []
            for k, v in options[r_index * cols:(r_index + 1) * cols]:
                tds.append(TD(INPUT(_type="checkbox", _name=field.name,
                         requires=attr.get("requires", None),
                         hideerror=True, _value=k,
                         value=(str(k) in values)), v))
            opts.append(TR(tds))

        if opts:
            opts[-1][0][0]["hideerror"] = False
        return TABLE(*opts, **attr)

# -----------------------------------------------------------------------------
class S3AddPersonWidget(FormWidget):
    """
        Renders a person_id field as a Create Person form,
        with an embedded Autocomplete to select existing people.

        It relies on JS code in static/S3/s3.select_person.js
    """

    def __init__(self, select_existing = True):
        self.select_existing = select_existing

    def __call__(self, field, value, **attributes):

        db = current.db
        T = current.T

        request = current.request
        response = current.response
        session = current.session

        formstyle = response.s3.crud.formstyle

        # Main Input
        real_input = str(field).replace(".", "_")
        default = dict(_type = "text",
                       value = (value != None and str(value)) or "")
        attr = StringWidget._attributes(field, default, **attributes)
        attr["_class"] = "hidden"

        if self.select_existing:
            _class ="box_top"
        else:
            _class = "hidden"

        # Select from registry buttons
        select_row = TR(TD(A(T("Select from registry"),
                             _href="#",
                             _id="select_from_registry",
                             _class="action-btn"),
                           A(T("Remove selection"),
                             _href="#",
                             _onclick="clear_person_form();",
                             _id="clear_form_link",
                             _class="action-btn hide",
                             _style="padding-left:15px;"),
                           A(T("Edit Details"),
                             _href="#",
                             _onclick="edit_selected_person_form();",
                             _id="edit_selected_person_link",
                             _class="action-btn hide",
                             _style="padding-left:15px;"),
                           IMG(_src="/%s/static/img/ajax-loader.gif" % \
                                    request.application,
                               _height=32,
                               _width=32,
                               _id="person_load_throbber",
                               _class="throbber hide",
                               _style="padding-left:85px;"),
                           _class="w2p_fw"),
                        TD(),
                        _id="select_from_registry_row",
                        _class=_class,
                        _controller=request.controller,
                        _field=real_input,
                        _value=str(value))

        # Autocomplete
        select = "select_person($('#%s').val());" % real_input
        widget = S3PersonAutocompleteWidget(post_process=select)
        ac_row = TR(TD(LABEL("%s: " % T("Name"),
                             _class="hide",
                             _id="person_autocomplete_label"),
                       widget(field,
                              None,
                              _class="hide")),
                    TD(),
                    _id="person_autocomplete_row",
                    _class="box_top")

        # Embedded Form
        ptable = db.pr_person
        ctable = db.pr_contact
        fields = [ptable.first_name,
                  ptable.middle_name,
                  ptable.last_name,
                  ptable.date_of_birth,
                  ptable.gender]

        if request.controller == "hrm":
            fields.append(ptable.occupation)
            emailRequired = current.deployment_settings.get_hrm_email_required()
        else:
            emailRequired = False
        if emailRequired:
            validator = IS_EMAIL()
        else:
            validator = IS_NULL_OR(IS_EMAIL())

        fields.extend([Field("email",
                             notnull=emailRequired,
                             requires=validator,
                             label=T("Email Address")),
                       Field("mobile_phone",
                             label=T("Mobile Phone Number"))])

        labels, required = s3_mark_required(fields)
        if required:
            response.s3.has_required = True

        form = SQLFORM.factory(table_name="pr_person",
                               labels=labels,
                               formstyle=formstyle,
                               upload="default/download",
                               separator = "",
                               *fields)
        trs = []
        for tr in form[0]:
            if not tr.attributes["_id"].startswith("submit_record"):
                if "_class" in tr.attributes:
                    tr.attributes["_class"] = "%s box_middle" % tr.attributes["_class"]
                else:
                    tr.attributes["_class"] = "box_middle"
                trs.append(tr)

        table = DIV(*trs)

        # Divider
        divider = TR(TD(_class="subheading"),
                     TD(),
                    _class="box_bottom")

        # JavaScript
        if session.s3.debug:
            script = "s3.select_person.js"
        else:
            script = "s3.select_person.min.js"

        response.s3.scripts.append( "%s/%s" % (response.s3.script_dir, script))

        # Overall layout of components
        return TAG[""](select_row,
                       ac_row,
                       table,
                       divider)

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
class S3HumanResourceAutocompleteWidget(FormWidget):
    def __init__(self,
                 post_process = "",
                 delay = 450,   # milliseconds
                 min_length=2): # Increase this for large deployments

        self.post_process = post_process
        self.delay = delay
        self.min_length = min_length

    def __call__(self, field, value, attributes):
        return S3GenericAutocompleteTemplate(
            post_process = self.post_process,
            delay = self.delay,
            min_length = self.min_length,
            attributes = attributes,
            field = field,
            value = value,
            name_getter = "function (item) { alert(item.represent); return item.represent; }",
            id_getter = "function (item) { alert(item.id);  return item.id }",
            transform_value = lambda value: value,
            source = (
                "function (request, response) {"
                    "$.ajax({"
                        "url: S3.Ap.concat('/hrm/human_resource/search.acjson?"
                            "simple_form=True"
                            "&human_resource_search_simple_simple='+request.term+'"
                            "&get_fieldname=person_id"
                        "'),"
                        "dataType: 'json',"
                        "success: response"
                    "});"
                "}"
            )
        )

# -----------------------------------------------------------------------------
class S3AutocompleteOrAddWidget(FormWidget):
    """This widget searches for or adds an object. It contains:
    
    - an autocomplete field which can be used to search for an existing object.
    - an add widget which is used to add an object. 
        It fills the field with that object after successful addition
    """
    def __init__(
        self,
        autocomplete_widget,
        add_widget
    ):
        self.autocomplete_widget = autocomplete_widget
        self.add_widget = add_widget
        
    def __call__(self, field, value, **attributes):
        return TAG[""](
            # this does the input field
            self.autocomplete_widget(field, value, **attributes),
            
            # this can fill it if it isn't autocompleted
            self.add_widget(field, value, **attributes)
        )

# -----------------------------------------------------------------------------
class S3AddObjectWidget(FormWidget):
    """This widget displays an inline form loaded via AJAX on demand.
    
    In the browser:
        A load request must made to this widget to enable it.
        The load request must include:
            - a URL for the form
    
        after a successful submission, the response callback is handed the 
        response.
    """
    def __init__(
        self,
        form_url,
        table_name,
        
        dummy_field_selector,
        on_show,
        on_hide
    ):
        self.form_url = form_url
        self.table_name = table_name

        self.dummy_field_selector = dummy_field_selector
        self.on_show = on_show
        self.on_hide = on_hide

    def __call__(self, field, value, **attributes):
        s3 = current.response.s3
        T = current.T
        
        script_name = "%s/%s" % (
                s3.script_dir,
                [
                    "jquery.ba-resize.min.js",
                    "jquery.ba-resize.js",
                ][current.deployment_settings.base.debug]
            )

        if script_name not in s3.scripts:
            s3.scripts.append(script_name)
        return TAG[""](
            # @ToDo: this might be better moved to its own script.
            SCRIPT("""
$(function () {
    var form_field = $('#%(form_field_name)s')
    var throbber = $('<div id="%(form_field_name)s_ajax_throbber" class="ajax_throbber"/>')
    throbber.hide()
    throbber.insertAfter(form_field)

    function request_add_form() {
        throbber.show()
        var dummy_field = $('%(dummy_field_selector)s')
        // create an element for the form
        var form_iframe = document.createElement('iframe')
        var $form_iframe = $(form_iframe)
        $form_iframe.attr('id', '%(form_field_name)s_form_iframe')
        $form_iframe.attr('frameborder', '0')
        $form_iframe.attr('scrolling', 'no')
        $form_iframe.attr('src', '%(form_url)s')
        
        var initial_iframe_style = {
            width: add_object_link.width(),
            height: add_object_link.height()
        }
        $form_iframe.css(initial_iframe_style)
        
        function close_iframe() {
            $form_iframe.unload()
            form_iframe.contentWindow.close()
            //iframe_controls.remove()
            $form_iframe.animate(
                initial_iframe_style,
                {
                    complete: function () {
                        $form_iframe.remove()
                        add_object_link.show()
                        %(on_hide)s
                        dummy_field.show()
                    }
                }
            )
        }
        
        function reload_iframe() {
            form_iframe.contentWindow.location.reload(true)
        }

        function resize_iframe_to_fit_content() {
            var form_iframe_content = $form_iframe.contents().find('body');
            // do first animation smoothly
            $form_iframe.animate(
                {
                    height: form_iframe_content.outerHeight(true),
                    width: 500
                },
                {
                    duration: jQuery.resize.delay,
                    complete: function () {
                        // iframe's own animations should be instant, as they 
                        // have their own smoothing (e.g. expanding error labels)
                        function resize_iframe_to_fit_content_immediately() {
                            $form_iframe.css({
                                height: form_iframe_content.outerHeight(true),
                                width:500
                            })
                        }
                        // if the iframe content resizes, resize the iframe
                        // this depends on Ben Alman's resize plugin
                        form_iframe_content.bind(
                            'resize',
                            resize_iframe_to_fit_content_immediately
                        )
                        // when unloading, unbind the resizer (remove poller)
                        $form_iframe.bind(
                            'unload',
                            function () {
                                form_iframe_content.unbind(
                                    'resize',
                                    resize_iframe_to_fit_content_immediately
                                )
                                //iframe_controls.hide()
                            }
                        )
                        // there may have been content changes during animation
                        // so resize to make sure they are shown.
                        form_iframe_content.resize()
                        //iframe_controls.show()
                        %(on_show)s
                    }
                }
            )
        }
        
        function iframe_loaded() {
            dummy_field.hide()
            resize_iframe_to_fit_content()
            form_iframe.contentWindow.close_iframe = close_iframe
            throbber.hide()
        }
        
        $form_iframe.bind('load', iframe_loaded)
        
        function set_object_id() {
            // the server must give the iframe the object 
            // id of the created object for the field
            // the iframe must also close itself.
            var created_object_representation = form_iframe.contentWindow.created_object_representation
            if (created_object_representation) {
                dummy_field.val(created_object_representation)
            }
            var created_object_id = form_iframe.contentWindow.created_object_id
            if (created_object_id) {
                form_field.val(created_object_id)
                close_iframe()
            }
        }
        $form_iframe.bind('load', set_object_id)
        add_object_link.hide()

        /*
        var iframe_controls = $('<span class="iframe_controls" style="float:right; text-align:right;"></span>')
        iframe_controls.hide()

        var close_button = $('<a>%(Close)s </a>')
        close_button.click(close_iframe)
        
        var reload_button = $('<a>%(Reload)s </a>')
        reload_button.click(reload_iframe)

        iframe_controls.append(close_button)
        iframe_controls.append(reload_button)
        iframe_controls.insertBefore(add_object_link)
        */
        $form_iframe.insertAfter(add_object_link)
    }
    var add_object_link = $('<a>%(Add)s</a>')
    add_object_link.click(request_add_form)
    add_object_link.insertAfter(form_field)
})""" % dict(
            field_name = field.name,
            form_field_name = "_".join((self.table_name, field.name)),
            form_url = self.form_url,
            dummy_field_selector = self.dummy_field_selector(self.table_name, field.name),
            on_show = self.on_show,
            on_hide = self.on_hide,
            Add = T("Add..."),
            Reload = T("Reload"),
            Close = T("Close"),
        )
            )
        )


# -----------------------------------------------------------------------------
class S3SearchAutocompleteWidget(FormWidget):
    """
        Uses the s3Search Module

        @author: Michael Howden (michael@aidiq.com)
    """

    def __init__(self,
                 tablename,
                 represent,
                 get_fieldname = "id",
                 ):

        self.get_fieldname = get_fieldname
        self.tablename = tablename
        self.represent = represent

    def __call__(self, field, value, **attributes):

        request = current.request
        response = current.response
        session = current.session

        tablename = self.tablename

        modulename, resourcename = tablename.split("_", 1)

        s3_script_dir = "/%s/static/scripts/S3" % request.application
        if session.s3.debug:
            response.s3.scripts.append( "%s/s3.search.js" % s3_script_dir )
        else:
            response.s3.scripts.append( "%s/s3.search.min.js" % s3_script_dir )

        attributes["is_autocomplete"] = True
        attributes["fieldname"] = field.name
        attributes["get_fieldname"] = self.get_fieldname

        # Display in the simple search widget
        if value:
            attributes["value"] = self.represent(value)
        else:
            attributes["value"] = ""

        r = current.manager.parse_request(modulename, resourcename, args=[])
        search_div = r.resource.search( r, **attributes)["form"]
        #search_div = response.s3.catalog_item_search( r, **attributes)["form"]

        hidden_input = INPUT(value = value or "",
                             requires = field.requires,
                             _id = "%s_%s" % (tablename, field.name),
                             _class = "hidden_input",
                             _name = field.name,
                             _style= "display: none;",
                            )

        return TAG[""](
                    search_div,
                    hidden_input
                    )


# -----------------------------------------------------------------------------
class S3TimeIntervalWidget(FormWidget):
    """
        Simple time interval widget for the scheduler task table
    """

    multipliers = (("weeks", 604800),
                   ("days", 86400),
                   ("hours", 3600),
                   ("minutes", 60),
                   ("seconds", 1))

    @staticmethod
    def widget(field, value, **attributes):

        T = current.T
        multipliers = S3TimeIntervalWidget.multipliers

        if value is None:
            value = 0

        if value == 0:
            multiplier = 1
        else:
            for m in multipliers:
                multiplier = m[1]
                if int(value) % multiplier == 0:
                    break

        options = []
        for i in xrange(1, len(multipliers) + 1):
            title, opt = multipliers[-i]
            if opt == multiplier:
                option = OPTION(title, _value=opt, _selected="selected")
            else:
                option = OPTION(title, _value=opt)
            options.append(option)

        val = value / multiplier
        inp = DIV(INPUT(value = val,
                        requires = field.requires,
                        _id = ("%s" % field).replace(".", "_"),
                        _name = field.name),
                  SELECT(options,
                         _name=("%s_multiplier" % field).replace(".", "_")))
        return inp

    @staticmethod
    def represent(value):

        T = current.T
        multipliers = S3TimeIntervalWidget.multipliers

        try:
            val = int(value)
        except:
            val = 0

        if val == 0:
            multiplier = multipliers[-1]
        else:
            for m in multipliers:
                if val % m[1] == 0:
                    multiplier = m
                    break

        val = val / multiplier[1]
        return "%s %s" % (val, T(multiplier[0]))

# END =========================================================================
