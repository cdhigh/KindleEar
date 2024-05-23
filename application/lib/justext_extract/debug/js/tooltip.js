 
var details = [];

//include
$("head").append('<link rel="stylesheet" type="text/css" href="' + 'js/jquery.qtip.min.css' + '" />');
//$("head").append('<script type="text/javascript" src="' + 'js/jquery.min.js' + '"></script>');
//$("head").append('<script type="text/javascript" src="' + 'js/jquery.qtip.min.js' + '"></script>');


function getContent(id){
	for(var i=0; i<details.length; i++){
		if (details[i].id == id)
			return details[i].parameters;
	}
	return 0;
}

function createBubble(c){
	var html = '';
	if (c == 0)
		return 'no tooltip text found';
	html += '<table class="tooltip '+c.final_class+'">\
	<tr class="odd"><td class="attr">final class</td><td class="value">'+c.final_class+'</td></tr>\
	<tr class="even"><td class="attr">context-free class</td><td class="value">'+c.context_free_class+'</td></tr>\
	<tr class="odd"><td class="attr">heading</td><td class="value">'+c.heading+'</td></tr>\
	<tr class="even"><td class="attr">length (in characters)</td><td class="value">'+c.length+'</td></tr>\
	<tr class="odd"><td class="attr">number of characters within links</td><td class="value">'+c.characters_within_links+'</td></tr>\
	<tr class="even"><td class="attr">link density</td><td class="value">'+c.link_density+'</td></tr>\
	<tr class="odd"><td class="attr">number of words</td><td class="value">'+c.number_of_words+'</td></tr>\
	<tr class="even"><td class="attr">number of stopwords</td><td class="value">'+c.number_of_stopwords+'</td></tr>\
	<tr class="odd"><td class="attr">stopword density</td><td class="value">'+c.stopword_density+'</td></tr>\
	<tr class="even"><td colspan="2" class="value">'+c.dom+'</td></tr>\
	<tr class="odd"><td colspan="2" class="value">'+c.other+'</td></tr>\
	<tr class="even"><td colspan="2" class="value">'+c.reason+'</td></tr>\
	</table>';
	return html;
}
$(document).ready(function()
{
	// Match all <A/> links with a title tag and use it as the content (default).
	//alert('hello');
	//$('p[qtip]').qtip();
	//$('p[title]').qtip();
	//$('p').qtip();
	$('[qtip-content]').qtip(
	{
		content: { 
			text: function(api) {
			// Retrieve content from custom attribute of the $('.selector') elements.
				var p = getContent($(this).attr('qtip-content'));
				$(this).qtip('option', 'style.classes', 'qtip-shadow qtip-' + (p.final_class == 'good' ? 'green' : 'red'));
				return createBubble(p);
			},
			title: {
						text: 'Paragraph details',
						button: false
					}
			//attr: 'id' // Use the ALT attribute of the area map for the content
		},
		style: {
			classes: //'qtip-shadow qtip-green'
			function(api) {
				for(var i=0; i<details.length; i++){
					if (details[i].id == $(this).attr('qtip-content'))
						return details[i].final_class == 'good' ? 'qtip-shadow qtip-green' : 'qtip-shadow qtip-red';
				}
				return 'qtip-shadow qtip-green';
			// Retrieve content from custom attribute of the $('.selector') elements.
				//return getContent($(this).attr('qtip-content'));
			}
		},
		position: {
			my: 'top-left',
			at: 'bottom-left'
			//my: function(){ return this.context.localName=='a' ? 'top-left' : 'center'},
			//at: function(){ return this.context.localName=='a' ? 'bottom-left' : 'center'}
		}
	});
});
