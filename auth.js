let supa;

async function boothauth() {
    const response = await fetch("/api/config");
    const config = await response.json();

    supa = supabase.createClient(config.url, config.key);
    supa.auth.onAuthStateChange((event, session) =>{
        if(event === "SIGNED_IN" && session){
            alert("auth successful!"+session.user.email)
            window.location.href = "dash.html";
        }
    });
}

boothauth();

document.getElementById("loginForm").addEventListener("submit",async(event)=>{
    event.preventDefault();

    const emailValue = document.getElementById("email").value;
    const passwordValue = document.getElementById("password").value;

    const {data, error} = await supa.auth.signInWithPassword(
        {
            email: emailValue,
            password : passwordValue
        }
    );

    if(error){
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
})

supa.auth.onAuthStateChange((event, session) =>{
    if(event === "SIGNED_IN" && session){
        alert("auth successful!"+session.user.email)
        window.location.href = "dash.html";
    }
})
