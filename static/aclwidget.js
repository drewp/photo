$(function () {
    $(".aclWidget button").click(function () {
	$(this).closest(".aclWidget").find(".expandable").toggle();
	return false;
    });
    function spin(result) {
	result.text("sending.. ");
	result.append($('<img class="spinner" src="/static/snake-spinner.gif"/>'));
    }
    function onCheckbox() {
	var check = $(this);
	var agent = check.attr('about');
	var accessTo = check.closest("form").attr("about");
	var op = check.is(":checked") ? "allow" : "deny";
	var result = $(this).parent().find(".result");
	spin(result);
	$.post("/aclChange", {agent: agent, accessTo: accessTo, op: op}, 
	       function (data) {
		   result.text(data.msg);
		   if (data.agentState) {
		       check[0].checked = true;
		       check.attr("checked", "checked");
		   } else {
		       check[0].checked = false;
		       check.removeAttr("checked");
		       // need to update the creation rows too
		   }
	       });
	return false;
    }
    $("input[type=checkbox].acl-set").change(onCheckbox).click(onCheckbox);
});
