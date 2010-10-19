$(window).load(function () {


    $(".frame").mouseenter(function () {
	var lastLi = $(this).find('.commentSpace li.newCommentRow');
	$(".commentSpace li.newCommentRow").not(lastLi).fadeTo(100, 0);
	lastLi.fadeTo(500, 1);
    });
    $(".commentSpace li.newCommentRow").fadeTo(0, 0);

});
