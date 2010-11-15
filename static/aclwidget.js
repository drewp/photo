$(function () {
    $(".aclWidget button").click(function () {
	$(this).closest(".aclWidget").find(".expandable").toggle();
	return false;
    });
    function onCheckbox() {
	var check = $(this);
	var agent = check.attr('about');
	var accessTo = check.closest("form").attr("about");
	var op = check.is(":checked") ? "allow" : "deny";
	var result = $(this).parent().find(".result");
	result.text("sending.. ");
	result.append($('<img class="spinner" src="/static/snake-spinner.gif"/>'));
	$.post("/aclChange", {agent: agent, accessTo: accessTo, op: op}, 
	       function (data) {
		   console.log("data", data);
		   result.text(data.msg);
		   check.attr('checked', data.agentState);
	       });
	return false;
    }
    $("input[type=checkbox].acl-set").change(onCheckbox).click(onCheckbox);
});