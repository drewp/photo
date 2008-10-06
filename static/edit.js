/*
todo: 
OK keyboard for row copy
OK visual row copy feedback
OK don't leave if they press enter on the form
#imagePreview should always hover in the top right, and get bigger with the browser
stop the n^2 regen of the statements all the time
drag multiple rows to check them faster
brick-layout the images so they can be bigger. highlight rows on hover.
click existing columns to edit their params
only offer to save if we're logged in (but show stmts always)
don't send rdfs:label unless this is a newly created thing that we made some use of
complete on already-used tags. show usage: "2008/picnic (3 photos)"
scroll table internally, hold headers: http://www.imaputz.com/cssStuff/bigFourVersion.html
if we already used an initial for a column, look for a different one
face detect and zoom on those
disallow selection on the tag cells
get imgs by sparql, including the POST resource to send results back to
make copyrow widget disappear if we're at the bottom or haven't started
click outside addColumn to make it disappear
flickr interface- query your flickr images through the flickr gateway, tag them here

*/

var photo = (function() {
    // I'm using this format for the rdf in js: 
    // http://n2.talis.com/wiki/RDF_JSON_Specification

    // though this looks nice too: http://n2.talis.com/wiki/RDF_JSON_Brainstorming#ARC_triples_array_in_PHP_structure
    

    var lastRow = 0;

    function cellToggle(cell) {
	if (cell.hasClassName('selected-stmts')) {
	    cellUnchecked(cell);
	} else {
	    cellChecked(cell);
	}
    }

    function cellChecked(cell) {
	cell.addClassName('selected-stmts');
//	cell.innerHTML = '[X]';
    }
    function cellUnchecked(cell) {
	cell.removeClassName('selected-stmts');
//	cell.innerHTML = '[ ]';
    }

    return {
	getStatements: function () {
	    /* js/rdf for all the 'stmts' attrs on elements with the
	'selected-stmts' class */
	    var ret = [];
	    $$(".selected-stmts").each(function(elem) {
		ret.push(elem.getAttribute('stmts').evalJSON())
	    });
	    $('statements').innerHTML = $A(ret).toJSON();
	    return ret;
	},
	setLastRow: function(tr) {
	    /* note the last-clicked row, so the user can request a copy
      	       of its values to the next row. Update the UI tip */
	    lastRow = tr;
	    

	    $('copy-row').setStyle('top: '+tr.offsetTop+'px');
	},

	addColumn: function(obj, label, predicate, classUri) {
	    /* add a table column for a new tag obj */
	    $('tagger').getElementsBySelector('tr').each(function(tr, i) {
		if (i == 0) {
		    var stmts = {};
		    stmts[obj] = {'http://www.w3.org/2000/01/rdf-schema#label': 
				  [{type: 'literal', value: label}]}
		    if (classUri != null) {
			stmts[obj][
			    'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
			] = [{type: 'uri', value: classUri}]};
		    var th = new Element('th', {'class' : 'selected-stmts',
			'stmts' : $H(stmts).toJSON()}).insert(label);
		    var thAdd = tr.childElements().last();
		    thAdd.insert({ before: th });
		    
		} else {
		    var stmts = {};
		    stmts[tr.getAttribute('subj')] = {};
                    stmts[tr.getAttribute('subj')][predicate] = [{type: 'uri', value: obj}];

		    var td = new Element('td', {obj: obj, 
		        stmts: $H(stmts).toJSON()});

		    td.insert(label[0].toUpperCase());
		    Event.observe(td, 'click', function() {
			cellToggle(td); 
			photo.setLastRow(tr);
		    });
		    // also support dragging over cells

		    tr.appendChild(td);
		}
	    });
	},

	onAddForm: function() {
	    var f = $('addForm');
	    var class_ = f['class'].getValue();
	    var label = f['label'].getValue();
	    var uri = f['uri'].getValue();
	    photo.addColumn(uri, label, "http://xmlns.com/foaf/0.1/depicts", 
			    class_);
	    photo.hideAddColumn();
	},

	postStatements: function() {
	    var stmts = photo.getStatements();
	    new Ajax.Request('saveStatements', {
		method: 'post',
		contentType: 'application/json',
		postBody: stmts.toJSON(),
		onSuccess: function(transport) {
		    console.log("successfully saved", transport.responseText);
		    // then move back to some non-edit page so they
		    // don't save the stmts again
		}
	    });
	},
	updateTagUrl: function () {
	    var cls = $('addForm')['class'].getValue();
	    var clsWord = /\/([^\/]+)$/.exec(cls)[1].toLowerCase();
	    var label = $('addForm')['label'].getValue();

	    label = label.replace(/(\w)\s+(\w)/g, "$1-$2").toLowerCase().camelize()

	    var newUri = "http://photo.bigasterisk.com/2008/" + clsWord + "/" + encodeURIComponent(label);
	    $('addForm')['uri'].value = newUri;
	},

	showAddColumn: function() { 
	    Element.show('addTag');
	  //broken?  Form.Element.focus('addColumnLabel').clear();
	},
	hideAddColumn: function() {
	    Element.hide('addTag');
	},

	toggleAddColumn: function () {
	    if ($('addTag').visible()) {
		photo.hideAddColumn();
	    } else {
		photo.showAddColumn();
	    }
	},

	copyToNextRow: function() {
	    /* copy the lastRow settings to the next row */
	    var nextRow = lastRow.next();
	    if (nextRow == null) {
		return;
	    }
	    var lastTds = lastRow.childElements();
	    var nextTds = nextRow.childElements();
	    // BUG: if we're bricking the photos, there's a variable
	    // number of leadup TD elements in the row, especially at
	    // the top. We need to look at only the later elements.
	    for (var i=0; i<lastTds.size(); i++) {
		if (lastTds[i].hasClassName('selected-stmts')) {
		    cellChecked(nextTds[i]);
		} else {
		    cellUnchecked(nextTds[i]);
		}
	    }
	    photo.setLastRow(nextRow);
	},
	showLarge: function (largePicUrl) {
	    $('largeImg').src = largePicUrl;
	}
    };
})();

Event.observe(window, "load", function() {
    
    photo.addColumn("http://photo.bigasterisk.com/0.1/friends",
		    "public",
		    "http://photo.bigasterisk.com/0.1/viewableBy",
		    null);
    photo.addColumn("http://photo.bigasterisk.com/2007/person/drew", 
		    "Drew", 
		    "http://xmlns.com/foaf/0.1/depicts",
		    "http://xmlns.com/foaf/0.1/Person");
    photo.addColumn("http://photo.bigasterisk.com/2007/person/kelsi", 
		    "Kelsi", 
		    "http://xmlns.com/foaf/0.1/depicts",
		    "http://xmlns.com/foaf/0.1/Person");
    photo.addColumn("http://photo.bigasterisk.com/2008/person/apollo", 
		    "Apollo", 
		    "http://xmlns.com/foaf/0.1/depicts",
		    "http://xmlns.com/foaf/0.1/Person");
    
    Event.observe($('addForm')['label'], 'change', photo.updateTagUrl);
    Event.observe($('addForm')['label'], 'keyup', photo.updateTagUrl);
    Event.observe($('addForm')['class'], 'change', photo.updateTagUrl);

    Event.observe(document, 'keypress', function(event) {
	if (event.charCode == 99 /* c */) {
	    photo.copyToNextRow();
	    return false;
	} else if(event.charCode == 97 /* a */) {
	    photo.showAddColumn();
	}
    });

    photo.setLastRow($('tagger').getElementsBySelector('tr')[5]);
});
