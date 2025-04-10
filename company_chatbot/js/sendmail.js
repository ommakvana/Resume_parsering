$(document).ready(function(){
	
	$("#send_mail").click(function(){
		var your_name = $("#name").val();
		var email_id = $("#email").val();
		var phone = $("#phone").val();
		var subject = $("#subject").val();
		var message = $("#message").val();

		var json_data = {
			"name" : your_name,
			"email" : email_id,
			"phone" : phone,
			"subject" : subject,
			"message" : message,
			"g-recaptcha-response":$("#g-recaptcha-response").val()
		}

		if(!your_name){
			alert("Please enter name");
			$("#name").focus();
			return;
		}
		if(!email_id){
			alert("Please enter email");
			$("#email").focus();
			return;
		}
		if(!phone){
			alert("Please enter phone");
			$("#phone").focus();
			return;
		}
		if(!subject){
			alert("Please enter subject");
			$("#subject").focus();
			return;
		}
		if(!message){
			alert("Please enter message");
			$("#message").focus();
			return;
		}

		if(!$("#g-recaptcha-response").val()){
			alert("Please verify you are not a robot");
			return;	
		}

		$("#send_mail").val("Sending .....");

		$.post("https://logbinary.com/sendmail.php", json_data, function(data, status){		    
		    if(status == "success"){
		    	$(".contact_form input[type='text']").val("");
		    	$(".contact_form textarea").val("");
		    	grecaptcha.reset();
		    	alert(data);
		    }else{
		    	alert("Unable to send message!! Please try again later.");
		    }
		    $("#send_mail").val("SEND MESSAGE");
		})

	});
});