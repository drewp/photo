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
	if (tt == 'TEXTAREA' || tt == 'INPUT') {
	    // no arrow key flips in the text boxes
	    return true;
	}
	if (e.which == 37) { 
	    document.location = arrowPages.prev;
	} else if (e.which == 39) {
	    document.location = arrowPages.next;
	}

    });

    $.get("/comments", 
	  {post: currentPhotoUri}, 
	  function (result) { 
	      $("#comments").html(result); 
	      $("#comments").removeAttr("style");
	  }, "html");



    function saveTagsAndDesc() {
	$("#saveStatus").text("");
	$("#saveMeta").attr('disabled', true);
	$.post("/tagging", {
	    img: currentPhotoUri,
	    tags: $("#tags").val(),
	    desc: $("#desc").val()}, 
	       function(data) { 
		   $("#saveStatus").text("ok");
		   refreshTagsAndDesc(data);
	       },
	       "json");
    };
    $("#saveMeta").click(saveTagsAndDesc);

    $("#tags,#desc").keypress(function(event) {

	// I mean to catch any change, including mouse paste
	$("#saveMeta").attr('disabled', false);

	if (event.keyCode == '13') {
	    saveTagsAndDesc();
	    event.preventDefault();
	    $("#tags,#desc").blur();
	    return false;
	}
	return true;
    });

    function refreshTagsAndDesc(data) {
	$("#tags").val(data.tagString);
	$("#desc").val(data.desc);
	$("#saveMeta").attr('disabled', true);

	$("#otherWithTag").empty();
	$.each(data.tags, function (i, tag) {
	    $("#otherWithTag").append("<div><a href=\"/set?tag="+tag+"\">"+tag+"</a></div>");
	});
	startNextImgPreload(); // try to do this after other work
    }

    $.getJSON("/tagging", 
	      {img: currentPhotoUri},
	      refreshTagsAndDesc);





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
	$.post('/makePublic', {uri: currentPhotoUri},
	       function(data, textStatus) {
		   button.replaceWith(data);
	       });
    });

    $("#tags").focus();
 
});

function flickrUpload() {
    var st = $("#flickrUpload");

    var sz = $("#flickrUpload input[name=size]:checked").val();
    st.html('Uploading... ' +
	    '<img class="spinner" src="static/snake-spinner.gif"/>');
    
    $.post("/flickrUpload/",
	   {img: currentPhotoUri,
	    size: sz,
	    test: ''}, 
	   function (data) {
	       st.html("Done: " +
		       "<a href=\""+data.flickrUrl+"\">flickr copy</a>");
	   }, "json");
}




