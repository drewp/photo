Polymer({
    is: "photo-related-links",
    properties: {
        img: {type: Object, notify: true},
        linksUrl: {computed: "_linksUrl(img)"},
        response: {type: Object, notify: true, observer: '_change'},
    },
    reload: function() {
        this.$.getLinks.generateRequest();
    },
    _linksUrl: function(img) {
        return img.uri.replace('http://', 'https://') + '/links'
    },
    ready: function() {
        
    },
    _change: function() {
        // need the elements to be ready since i'm still matching them with jquery
        setTimeout(this.setupRelatedPreviews.bind(this), 500);
    },
    relatedPreview: function(relatedLink) {
        // use preloadContents instead!
        var div = $("<div>").addClass("relatedPreview");
        div.append("loading...");
        window.getNewPageContents(relatedLink, function (data) {
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
    },

    setupRelatedPreviews: function() {
        $("#related li").each(function (i, li) {
            li = $(li);
            var previewDiv;
            li.hover(function () {
                previewDiv = this.relatedPreview(li.find("a").attr("href"));
	        var offset = li.offset();
                li.append(previewDiv);
	        li.addClass("previewing");
	        previewDiv.offset({left: offset.left - 563, 
				   top: offset.top - 28});
            }.bind(this), function () {
	        // this is removing when they hover over to the
	        // preview div, which is not what i want.
                previewDiv.remove();
	        li.removeClass("previewing");
            }.bind(this));
        }.bind(this));
    }

});
