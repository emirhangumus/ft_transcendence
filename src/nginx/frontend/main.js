const body = document.getElementById("body");
const REFRESH_TOKEN_INTERVAL = 1000 * 60 * 1; // 1 minutes

const ROUTES = parseRoutes({
    '/': {
        endpoint: '/api/v1'
    },
    '/login': {
        endpoint: '/api/v1/auth/login'
    },
    '/register': {
        endpoint: '/api/v1/auth/register'
    },
    '/friends': {
        endpoint: '/api/v1/friend'
    },
    '/chat': {
        endpoint: '/api/v1/chat'
    },
    '/chat/:id(6)': {
        endpoint: '/api/v1/chat/:id'
    },
    '/chat/new': {
        endpoint: '/api/v1/chat/new'
    },
    '/play': {
        endpoint: '/api/v1/play'
    },
    '/play/:id(6)': {
        endpoint: '/api/v1/play/:id'
    },
});

function makeScriptsExecutable() {

    // remove all the scripts that have been executed
    const executedScripts = Array.from(document.querySelectorAll('.executed-script'));
    executedScripts.forEach(script => {
        script.parentNode.removeChild(script);
    });

    const scripts = Array.from(document.querySelectorAll('script'));
    scripts.forEach(script => {
        const newScript = document.createElement('script');
        if (script.src) {
            // newScript.src = script.src;
            // newScript.classList.add('executed-script');
            // newScript.onload = () => {
            //     script.parentNode.removeChild(script); // Optional: remove the original script tag
            // };
        } else {
            newScript.classList.add('executed-script');
            newScript.textContent = script.textContent;
        }
        // remove
        script.parentNode.removeChild(script);
        console.log("Appending script", newScript);
        document.body.appendChild(newScript);
    });
  }

const [currentPath, setCurrentPath] = signal(window.location.pathname);

function disableAllAnchorTags() {
    const anchorTags = document.getElementsByTagName("a");
    for (let i = 0; i < anchorTags.length; i++) {
        anchorTags[i].addEventListener("click", (e) => {
            e.preventDefault();
            const newPath = anchorTags[i].getAttribute("href");
            setCurrentPath(newPath);
        });
    }
}

// override the default behavior of the browser
window.onpopstate = function () {
    setCurrentPath(window.location.pathname);
}

let MAX_TRIES = 3;

async function renewAccessToken() {
    const cookies = parseCookie(document.cookie);

    if (!cookies['refresh_token']) {
        return ;
    }

    const init = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'credentials': 'include',
        },
        body: JSON.stringify({
            refresh: cookies['refresh_token']
        })
    };

    let x = await fetch('/api/v1/auth/token/refresh/', init);

    try {
        x = await x.json();
        if (x.access) {
            setCookie('access_token', x.access, 3600000); 
        }
    } catch (e) {
        console.error("Failed to renew access token");
    }
}

setInterval(() => {
    renewAccessToken();
}, REFRESH_TOKEN_INTERVAL);

function setPage()
{
    console.log(ROUTES, currentPath());
    const path = getEndpoint(ROUTES, currentPath());
    console.log("->", path);
    if (path) {
        const cookies = parseCookie(document.cookie);

        const init = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'credentials': 'include',
            }
        };

        if (cookies['access_token']) {
            init.headers['Authorization'] = `Bearer ${cookies['access_token']}`;
        }

        fetch(path, init).then(async (res) => {
            const t = await res.text();

            try {
                const json = JSON.parse(t);
                if (json && json.code && json.code === 'token_not_valid') {
                    if (MAX_TRIES === 0) {
                        deleteAllCookies();
                        setCurrentPath('/login');
                        return ;
                    }
                    await renewAccessToken();
                    MAX_TRIES--;
                    setPage();
                    return ;
                }
                if (json && json.code && json.code === 'user_not_found') {
                    deleteAllCookies();
                    setCurrentPath('/login');
                    return ;
                }
            } catch (e) {
                // do nothing
            }

            body.innerHTML = t;
            disableAllAnchorTags();
            makeScriptsExecutable();
            MAX_TRIES = 3;
        })
    }
    else {
        body.innerHTML = "404 Not Found";
    }
}

effect(() => {
    console.log("Current path: ", currentPath());
    setPage();
    window.history.pushState({}, "", currentPath());
});

renewAccessToken().then(() => {
    console.log("Renewed access token");
});