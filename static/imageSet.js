$(function () {
    function slug(s) {
	s = s.replace(/^\s*/, "").replace(/\s*$/, "");
	s = s.replace(/[^a-zA-Z0-9\-_\s]/g, "");
	s = s.toLowerCase();
	s = s.replace(/[-_\s]+([a-z0-9])/ig,
		      function(z,b) { return b.toUpperCase();} );
	return s;
    }

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
	var sansStar = tagString.replace(/ \*(?= )/g, "");
	if (sansStar != tagString) {
	    $("#starTag").addClass("set");
	} else {
	    $("#starTag").removeClass("set");
	}
	sansStar = sansStar.replace(/^ +/, "").replace(/ +$/, "");
	$("#tags").val(sansStar);
    }

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

    function tagsOrDescChanged(event) {
	// I mean to catch any change, including mouse paste
	$("#saveMeta")[0].disabled = false;
	$("#saveMeta").removeAttr('disabled');

	if (event && event.keyCode == '13') {
	    saveTagsAndDesc();
	    $("#tags,#desc").blur();
	    return false;
	}
	return true;
    }

    function refreshTagsAndDesc(data) {
	setTags(data.tagString);
	$("#desc").val(data.desc);
	$("#saveMeta").attr("disabled", "disabled");
    }

    function refreshCurrentPhoto(uri) {
        /* light up this one in the photosInSet collection */
        $("#photosInSet > a > span.current").attr("class", "not-current");
        $("#photosInSet > a[about='"+uri+"'] > span").attr("class", "current");
    }

    function updateSections(data) {
	$.each(data, function (tmpl, contents) {
            try {
		if (tmpl == "title") {
		    $("title").text(contents);
                } else if (tmpl == "pageJson") {
                    // needs to be folded into one object
                    var d = contents.pageJson;
                    picInfo = JSON.parse(d.picInfo);
                    arrowPages = {prev: JSON.parse(d.prev), 
                                  next: JSON.parse(d.next)};
                    allTags = JSON.parse(d.allTags);
		} else {
		    var newHtml = Mustache.to_html(templates[tmpl], contents);
		    // tmpl: topBar, featured, featuredMeta, photosInSet, preload, pageJson
                    try {
                        $("#"+tmpl).html(newHtml);
                    } catch (e) {
                        console.log("templating failed", tmpl, newHtml);
                    }
                }
            } catch (e) {
                console.log("outer fail", tmpl);
            }
	});

    }

    var _preloaded = {};
    function preloadNext() {
        var p = $(".nextClick").attr("nextclick")
        getNewPageContents(p, function (data) { _preloaded[p] = data });
    }

    function getNewPageContents(newPath, cb) {
        if (_preloaded[newPath]) {
            cb(_preloaded[newPath]);
            return;
        }
	$.ajax({
            url: newPath, 
            // should be an Accept header (or a different resource, if
            // we're going to do this in pieces?) but i don't have the
            // jquery docs on the plane right now
            data: {"jsonUpdate":"1"}, 
            success: function (data) {
                cb(data);
            }
        });
    }

    function gotoPage(newPath) {
        getNewPageContents(newPath, function (data) {
            updateSections(data);
            // maybe this doesnt have to wait for the new data?
            var loc = window.location;
            window.history.pushState({}, document.title, 
                                     loc.protocol + '//' + loc.host + newPath);
            refresh.main();
        });
    }

    var templates = {};
    $.getJSON("/templates", function (t) {
        templates = t.templates;
    });


    var refresh = {
        main: function () {

            $(".expand").click(function () {
	        $(this).next().toggle('fast');
	        return false;
            }).next().hide();

            $("#rangeStart button").click(function() {
	        startImagePick("range start", function(picked) {
	            $("#rangeStart .pick").text(picked.closest("a").attr("about"));
	            $("#rangeStart img").attr("src", $(picked).attr("src"));
	        });
            });

            $("#rangeEnd button").click(function() {
	        startImagePick("range end", function(picked) {
	            $("#rangeEnd .pick").text(picked.closest("a").attr("about"));
	            $("#rangeEnd img").attr("src", $(picked).attr("src"));
	        });
            });

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
	          }, "html");

            $("#starTag").click(function () {
	        $("#starTag").toggleClass("set");
	        tagsOrDescChanged();
	        saveTagsAndDesc();
            });
            $("#saveMeta").click(saveTagsAndDesc);

            $("#tags,#desc").keypress(function(event) {
	        return tagsOrDescChanged(event);
            });

            refreshTagsAndDesc(picInfo.tags);

            setGlobalTags(allTags);
            $("#tags").tagSuggest({});

            $("#featuredPic div.nextClick").click(function () { 
                // i could preload this whole set of template results as well
                // as the images inside them
                var newPath = $(this).attr("nextclick");
                gotoPage(newPath);
                return false;
            });

            // should be a live bind (most of these should)
            $("#photosInSet > a").click(function () {
                gotoPage($(this).attr("href"));
                return false;
            });

            $("#ajaxError").ajaxError(function (event, xhr, ajaxOptions) {
	        if (!xhr.responseText) {
	            return;
	        }
	        $(this).show();
	        $(this).append("<p>Ajax error: "+xhr.responseText+"</p>");
            });

            $("#tags").focus();
            refreshCurrentPhoto(picInfo.currentPhotoUri);
            preloadNext();
        }
    };
    refresh.main();
    $(document).scrollTop(0);
});

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

function makePublicShare() {
    $.post("/aclChange", {accessTo: picInfo.currentPhotoUri, 
			  agent: "http://xmlns.com/foaf/0.1/Agent", 
			  op: "allow"}, 
	   function (data) {
	       
	       // need to invalidate the ACL dropdown now

	       var longUri = picInfo.currentPhotoUri+"/single";
	       $.getJSON("/shortener/shortLink", {long: longUri}, 
			 function (data) {
			     $("#publicShare").html($("<a>")
						    .attr("href", 'http://bigast.com/_'+data.short)
						    .text("Public share link"));
			 });
	   });
}

