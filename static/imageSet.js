$(function () {
    function slug(s) {
	s = s.replace(/^\s*/, "").replace(/\s*$/, "");
	s = s.replace(/[^a-zA-Z0-9\-_\s]/g, "");
	s = s.toLowerCase();
	s = s.replace(/[-_\s]+([a-z0-9])/ig, 
		      function(z,b) { return b.toUpperCase();} );
	return s;
    }

    $(".expand").click(function () { 
	$(this).next().toggle('fast');
	return false;
    }).next().hide();

    function startImagePick(msg, cb) {
	$("#rangeState").text("Click an image to pick " + msg);
	$("body,img").css("cursor", "crosshair");
	$("img").bind("click", function () {
	    stopImagePick();
	    cb(this);
	    return false;
	});
    }
    function stopImagePick() {
	$("img").unbind("click");
	$("body,img").css("cursor", "");
	$("#rangeState").text("");
    }

    function uriFromImg(el) {
	return 'http://photo.bigasterisk.com' + $(el).attr('src').replace(/\?.*/, "");
    }

    $("#rangeStart button").click(function() {
	startImagePick("range start", function(picked) {
	    $("#rangeStart .pick").text(uriFromImg(picked));
	    $("#rangeStart img").attr("src", $(picked).attr("src"));
	});
    });

    $("#rangeEnd button").click(function() {
	startImagePick("range end", function(picked) {
	    $("#rangeEnd .pick").text(uriFromImg(picked));
	    $("#rangeEnd img").attr("src", $(picked).attr("src"));
	});
    });

    function updateTagUrl() {
	var cls = $('#addForm select[name=class]').val();
	var clsWord = /\/([^\/]+)$/.exec(cls)[1].toLowerCase();
	var label = $('#addForm input[name=label]').val();
	
	var newUri = ("http://photo.bigasterisk.com/" + 
		      (new Date()).getFullYear() + "/" + 
		      clsWord + "/" + 
		      encodeURIComponent(slug(label)));
	$('#add-uri').val(newUri);
    }
    $("#addForm select[name=class], #addForm input[name=label]"
     ).bind("keyup change", updateTagUrl);
    
    $("#submitRange").click(function () {
	$("#rangeState").text("saving...");
	$.post(document.location + "&tagRange=1", 
	       {start: $("#rangeStart .pick").text(), 
		end: $("#rangeEnd .pick").text(), 
		rdfClass: $('#addForm select[name=class]').val(),
		label: $("#addForm input[name=label]").val(), 
		uri: $("#addForm input[name=uri]").val()},
	       function (data, textStatus) {
		   $("#rangeState").html(data.msg);
	       }, "json");
    });



    function startNextImgPreload() {
	$("#preload").attr('src', preloadImg);
    }

    $(window).keydown(function (e) {
	var tt = e.target.tagName;
	if (!e.ctrlKey && (tt == 'TEXTAREA' || tt == 'INPUT')) {
	    // no arrow key flips in the text boxes (unless you add ctrl)
	    return true;
	}
	if (e.which == 37) { 
	    document.location = arrowPages.prev;
	} else if (e.which == 39) {
	    document.location = arrowPages.next;
	}

    });

    
    $("#commentsFade").fadeTo(0, 0);
    $.get(picInfo.relCurrentPhotoUri + "/comments", 
	  {}, 
	  function (result) { 
	      $("#comments").html(result); 
	      $("#commentsFade").fadeTo(500, 1);
	      loadDelayedImgs();
	      //startNextImgPreload(); // try to do this after other work
	  }, "html");

    function loadDelayedImgs() {
	$("img[delaySrc]").each(function (i, elem) {
	    elem = $(elem);
	    elem.attr("src", elem.attr("delaysrc"));
	    elem.removeAttr("delaysrc");
	});
    }

    function getTagString() {
	// turns star into a '*' tag
	return $("#tags").val() + ($("#starTag").hasClass("set") ? " *" : "");
    }
    function setTags(tagString) {
	// turns '*' tag into the star icon setting
	tagString = " " + tagString + " ";
	var sansStar = tagString.replace(/ \* /g, "");
	if (sansStar != tagString) {
	    $("#starTag").addClass("set");
	} else {
	    $("#starTag").removeClass("set");
	}
	$("#tags").val(sansStar);
    }
  
    $("#starTag").click(function () {
	$("#starTag").toggleClass("set");
	tagsOrDescChanged(false);
    });

    function saveTagsAndDesc() {
	$("#saveStatus").text("");
	$("#saveMeta").attr('disabled', true);
	$.ajax({
	    type: 'PUT',
	    url: picInfo.relCurrentPhotoUri + "/tags", 
	    data : {
		tags: getTagString(),
		desc: $("#desc").val()},
	    success: function(data) {
		$("#saveStatus").text("ok");
		refreshTagsAndDesc(data);
	    },
	    dataType: "json",
	});
    };
    $("#saveMeta").click(saveTagsAndDesc);

    function tagsOrDescChanged(pressedEnter) {
	// I mean to catch any change, including mouse paste
	$("#saveMeta").attr('disabled', false);
	tagsChanged();

	if (pressedEnter) {
	    saveTagsAndDesc();
	    event.preventDefault();
	    $("#tags,#desc").blur();
	    return false;
	}
	return true;
    }

    $("#tags,#desc").keypress(function(event) {
	return tagsOrDescChanged(event.keyCode == '13');
    });

    function refreshTagsAndDesc(data) {
	setTags(data.tagString);
	$("#desc").val(data.desc);
	$("#saveMeta").attr('disabled', true);

	    // not working with new links section yet
	$(".related-withTag").remove();
	$.each(data.tags, function (i, tag) {
	    var label = tag == "*" ? "{starred}" : tag;
	    $("#related").append(
		imageLinkListElem("withTag", "/set?tag="+tag, label));
	});
    }

    refreshTagsAndDesc(picInfo.tags);

    setGlobalTags(allTags);
    $("#tags").tagSuggest({});

    $("#ajaxError").ajaxError(function (event, xhr, ajaxOptions) {
	if (!xhr.responseText) {
	    return;
	}
	$(this).show();
	$(this).append("<p>Ajax error: "+xhr.responseText+"</p>");
    });

    $(".makePub").click(function() {
	var button = $(this);
	var params = {uri: picInfo.currentPhotoUri};
	if (button.hasClass("allPublic")) {
	    params = {allInSet: ""+document.location.pathname + document.location.search};
	}
	$.post('/makePublic', params,
	       function(data, textStatus) {
		   button.replaceWith(data);
	       });
    });

    $("#tags").focus();


});

function imageLinkListElem(kind, uri, label) {
    var li = $("<li>");
    var a = $("<a>");
    li.addClass("related-"+kind);
    a.attr('href', uri).text(label);
    li.text(kind + " ").append(a);
    return li;
}

function fillImageInfo() {
    $.each(picInfo.links.links, function (i, kind) {
	$.each(kind[1], function (i2, link) {
	    $("#related").append(
		imageLinkListElem(kind[0], link.uri, link.label));
	});
    });

    $("#debugRdf").attr('href', 'http://bang:8080/openrdf-workbench/repositories/photo/explore?' + $.param({resource: '<'+picInfo.currentPhotoUri+'>'}));

    if(picInfo.facts.factLines) {
	$.each(picInfo.facts.factLines, function (i, line) {
	    $("#facts ul").append($("<li>").text(line));
	});
    }

}
fillImageInfo(); // *before* page draw


function flickrUpload() {
    var st = $("#flickrUpload");

    var sz = $("#flickrUpload input[name=size]:checked").val();
    st.html('Uploading... ' +
	    '<img class="spinner" src="static/snake-spinner.gif"/>');

    $.post("/flickrUpload/",
	   {img: picInfo.currentPhotoUri,
	    size: sz,
	    test: ''}, 
	   function (data) {
	       st.html("Done: " +
		       "<a href=\""+data.flickrUrl+"\">flickr copy</a>");
	   }, "json");
}

function sflyUpload() {
    alert("not implemented")
}



