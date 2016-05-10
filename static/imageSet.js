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

    function refreshCurrentPhoto(uri) {
        /* light up this one in the photosInSet collection */
        $("#photosInSet > a > span.current").removeClass("current").addClass("not-current");
        $("#photosInSet > a[about='"+uri+"'] > span").addClass("current");
    }

    function rootUrl(url) {
        var loc = window.location;
        return url.replace(new RegExp("^" + loc.protocol + '//' + loc.host), '');
    }

    function rebuildThisPage() {
        var thisPath = rootUrl(window.location.pathname + window.location.search);
        // wrong: in the case of random set, putting tags on this
        // image changes the set for all the other images too
        delete _preloaded[thisPath];
        gotoPage(thisPath);
    }
    window.rebuildThisPage = rebuildThisPage;

    function relatedPreview(relatedLink) {
        // use preloadContents instead!
        var div = $("<div>").addClass("relatedPreview");
        div.append("loading...");
        getNewPageContents(relatedLink, function (data) {
            div.empty();
            $.each(data.photosInSet.photosInSet, function (i, thumb) {
                if (i > 5) {
                    return;
                }
                // could use the video-triangle on here. These should
                // also be links
                div.append($("<img>").attr("src", thumb.thumb.src));
            });
        });
        return div;
    }

    function setupRelatedPreviews() {
        $("#related > li").each(function (i, li) {
            li = $(li);
            var previewDiv;
            li.hover(function () {
                previewDiv = relatedPreview(li.find("a").attr("href"));
		var offset = li.offset();
                li.append(previewDiv);
		li.addClass("previewing");
		previewDiv.offset({left: offset.left - 563, 
				   top: offset.top - 28})
            }, function () {
		// this is removing when they hover over to the
		// preview div, which is not what i want.
                previewDiv.remove();
		li.removeClass("previewing");
            });
        });
    }

    function updateSections(data) {
	$.each(data, function (tmpl, contents) {

		if (tmpl == "title") {
		    $("title").text(contents);
                } else if (tmpl == "pageJson") {
                    // needs to be folded into one object
                    var d = contents.pageJson;
                    picInfo = JSON.parse(d.picInfo);
                    arrowPages = {prev: JSON.parse(d.prev), 
                                  next: JSON.parse(d.next)};
		    preloadImg = JSON.parse(d.preloadImg);
                } else if (tmpl == "client") {
                    // not a template
		} else {
		    var newHtml = Mustache.to_html(templates[tmpl], contents, templates);
                    $("#"+tmpl).html(newHtml);
                }
	});
    }

    function preloadImage(src) {
        var nextImg = new Image();
        nextImg.src = src;
        var progress = $("<span>").text("I");
        $("#activity").append(progress);
	//$("#loaded").append("preloading image "+src);
        $(nextImg).load(function (ev) { progress.remove(); });
    }

    var _preloaded = {};
    var _preloadStarted = {};
    function preloadContents(path) {
        if (_preloadStarted[path]) {
            return;
        }
        _preloadStarted[path] = true;
        getNewPageContents(path, function (data) { 

            // _preloaded might get big, and we should kill old
            // entries. Also they get invalid over time
            
            $("#loaded").append($("<div>").text(path));
        });
    }

    function getNewPageContents(newPath, cb, eb) {
        newPath = rootUrl(newPath);
        if (_preloaded[newPath]) {
            if (cb) {
                cb(_preloaded[newPath]);
            }
            return;
        }
        // this could run a preload that had already been launched but not finished yet
        var progress = $("<span>").text("P");
        $("#activity").append(progress);
	$.ajax({
            url: newPath, 
            // should be an Accept header (or a different resource, if
            // we're going to do this in pieces?) but i don't have the
            // jquery docs on the plane right now
            data: {"jsonUpdate":"1"},
            success: function (data) {
                progress.remove();
                data.client = {preloadTime: new Date()};
                _preloaded[newPath] = data;
                if (cb) {
                    cb(data);
                }
            },
            error: function (jqXHR, textStatus, errorThrown) {
                progress.remove();
                if (eb) {
                    eb(jqXHR, textStatus, errorThrown);
                }
            },
            isPreload: true
        });
    }

    var runningAjax = [];
    $.ajaxPrefilter(function (opts, orig, jqXHR) {
	runningAjax.push(jqXHR);
    });
    function stopAllAjax() {
	$.each(runningAjax, function (i, j) { j.abort() });
	runningAjax = [];
    }

    function pathFromWindow() {
	var loc = window.location;
	return rootUrl(loc.href);
    }

    function gotoPage(newPath) {
	stopAllAjax();

        $("body").css("cursor", "wait"); // doesn't work on the nextClick image!
	var loading = $("<span>").text("Loading..");
	$("#activity").append(loading);
        var loc = window.location;

        var newUrl = loc.protocol + '//' + loc.host + newPath;

        function ajaxUpdateFailed() {
	    $("#activity").append($("<span>").text("Page reload"));
            window.location = newUrl;
            // cursor will reset itself
        }

        getNewPageContents(newPath, function (data) {
            try {
                updateSections(data);
            } catch (e) {
                ajaxUpdateFailed();
            }
            // maybe this doesnt have to wait for the new data?
            window.history.pushState({}, document.title, newUrl);
            // this is incomplete- i apparently need to watch for the browser going to this history and reconstruct the page state
            refresh.main();
            $("body").css("cursor", "auto");
	    loading.remove();
        }, function (x, s, e) {
	    loading.remove();
            ajaxUpdateFailed();
        });
    }

    var templates = {};
    $.getJSON("/templates", function (t) {
        templates = t.templates;
    });


    var refresh = {
        startup: function () {
            $(window).keydown(function (e) {
	        var tt = e.target.tagName.toUpperCase();
	        if (!e.ctrlKey && (tt == 'TEXTAREA' || tt == 'INPUT')) {
	            // no arrow key flips in the text boxes (unless you add ctrl)
	            return true;
	        }
	        if (e.which == 37) {
	            gotoPage(arrowPages.prev);
	        } else if (e.which == 39) {
	            gotoPage(arrowPages.next);
	        }

            });

            $("#ajaxError").ajaxError(function (e, jqxhr, settings, exception) {
                if (settings.isPreload) {
                    return;
                }
	        if (!jqxhr.responseText) {
	            return;
	        }
	        $(this).show();
	        $(this).append("<p>Ajax error: "+jqxhr.responseText+"</p>");
            });

            $(".expand").click(function () {
	        $(this).next().toggle('fast');
	        return false;
            }).next().hide();

	    function updateRange(rangeAttr, picked) {
	        rangeAttr.find(".pick").text(picked.closest("a").attr("about"));
	        rangeAttr.find("img").attr("src", picked.attr("src"));
	    }

            $("#rangeStart button").click(function() {
	        startImagePick("range start", function (picked) { 
		    updateRange($("#rangeStart"), $(picked)) });
            });

            $("#rangeEnd button").click(function() {
	        startImagePick("range end", function (picked) { 
		    updateRange($("#rangeEnd"), $(picked)) });
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
        },
        main: function () {
	    // some amount of page refresh has just happened

            $("#commentsFade").fadeTo(0, 0);
            if (picInfo.relCurrentPhotoUri) {
                $.get(picInfo.relCurrentPhotoUri + "/comments",
	              {},
	              function (result) {
	                  $("#comments").html(result);
	                  $("#commentsFade").fadeTo(500, 1);
	              }, "html");
            }

            // should be a live bind (most of these should)
            $(".iset").click(function () { 
                gotoPage($(this).attr("href"));
                return false;
            });

            $("#featuredPic div.nextClick").click(function () {
                gotoPage($(this).attr("nextclick"));
                return false;
            });

            refreshCurrentPhoto(picInfo.currentPhotoUri);
                       
	    if ($(".videoProgress").length) {
                // the json has a real flag for this, but I lost track
                // of who haas that json anymore
                if ($(".videoProgress").text().match(/fail/)) {
                    console.log("no reload");
                } else {
		    setTimeout(function () {
		        if ($(".videoProgress").length) {
			    var p = pathFromWindow();
			    delete _preloaded[p];
			    // this would be better as a reloader that
			    // only updated the featured image part. The
			    // part where the comment box reloads is
			    // especially annoying.
			    gotoPage(p);
		        }
		    }, 5000);
                }
	    }

            $(".iset.pl").each(function (i, elem) {
		// some of these are just too slow
                //preloadContents(elem.getAttribute("href"));
            });
	    preloadContents($(".iset.plPri").attr("href"));
            preloadImage(preloadImg);
            setupRelatedPreviews();
        }
    };
    refresh.startup();
    refresh.main();

    // this is to combat the autoscroll from focusing on tag widget. not sure where it goes
    //$(document).scrollTop(0);
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

