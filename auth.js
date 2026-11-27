let supa;

let captchaToken = null;

window.onTurnstileSuccess = function(token) {
    captchaToken = token;
};

async function boothauth() {
    const response = await fetch("/api/config");
    const config = await response.json();

    supa = supabase.createClient(config.url, config.key);
    supa.auth.onAuthStateChange((event, session) =>{
        if(event === "SIGNED_IN" && session){
            alert("auth successful!"+(session.user.email || session.user.user_metadata?.name ||"trial account"));
            window.location.href = "dash.html";
        }
    });
}

boothauth();

document.getElementById("loginForm").addEventListener("submit",async(event)=>{
    event.preventDefault();

    const emailValue = document.getElementById("email").value;
    const passwordValue = document.getElementById("password").value;

    if (!captchaToken) {
        alert("Please complete the CAPTCHA.");
        return;
    }

    const {data, error} = await supa.auth.signInWithPassword(
        {
            email: emailValue,
            password : passwordValue,
            options: {
                captchaToken
            }
        }
    );

    if(error){
        captchaToken = null;
        if(window.turnstile) window.turnstile.reset();
        alert("loginfailed:"+ error.message);
    }else{
        alert("login successful!")
        console.log("userdata:",data.user)
    }
});

document.getElementById("googlebtn").addEventListener("click", async()=>{
    const {error} = await supa.auth.signInWithOAuth({
        provider: "google",
        options:{
            redirectTo: window.location.origin
        }
    });
    if(error) alert("google login error:"+ error.message);
});

document.getElementById("githubbtn").addEventListener("click", async()=>{
    const {error} = await supa.auth.signInWithOAuth({
        provider: "github",
        options:{
            redirectTo: window.location.origin
        }
    });
    if(error) alert("github login error:"+ error.message);
});

document.getElementById("trial-btn").addEventListener("click", async () => {
    if (!captchaToken) {
        alert("Please wait for verification to finish.");
        return;
    }

    const trialName = `Guest_${Math.floor(1000 + Math.random() * 9000)}`;

    const { data, error } = await supa.auth.signInAnonymously({
        options: {
            captchaToken,
            data: {
                name: trialName,
                account_type: "trial"
            }
        }
    });

    if (error) {
        captchaToken = null;
        if (window.turnstile) turnstile.reset();
        alert("Trial login failed: " + error.message);
    }
});
