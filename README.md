
# Library.canonical.com

Library.canonical.com is a webpage designed to serve as a centralized source of truth for all corporate information within Canonical. It consolidates various forms of content stored in Google Drive and dynamically builds the site's structure based on the file structure in Google Drive. This project was initiated to address the challenge of scattered information across multiple sites, making it difficult to find the required information efficiently.


## Bugs, issues and contributions

If you have found a bug on the site or have an idea for a new feature, feel free to create a [new issue](https://github.com/canonical/library.canonical.com/issues/new), or suggest a fix by creating a [pull request](https://github.com/canonical/library.canonical.com/pulls). You can also find a link to create issues in the footer of every page of the site itself.


## Local development

It's simplest to run the site locally with [dotrun](https://github.com/canonical-web-and-design/dotrun/) and Docker.


### Setup

First, install the [requirements of dotrun](https://github.com/canonical/dotrun/blob/main/README.md#requirements).

Then, elevate the permissions of the Docker socket file:

```bash
sudo chmod 666 /var/run/docker.sock
```

Next, run the [dotrun installation script](https://github.com/canonical-web-and-design/dotrun/blob/main/README.md#installation).

Lastly, in your local copy of the project, the `.env.local` file needs the correct authentication tokens for your system to access the Library servers. Ask the project owner or another contributor to share them, then add them to the file.


### Develop interactively

Run the project with:

```bash
dotrun
```

Once the server has started, you can visit <http://0.0.0.0:8051> in your browser.

Run the SideNavigation:

```bash
cd sideNav
npm install
npm run dev
```

Once the server has started, you can visit <http://localhost:5173> in your browser.

## License

The content of this project is licensed under the [Creative Commons Attribution-ShareAlike 4.0 International license](https://creativecommons.org/licenses/by-sa/4.0/), and the underlying code used to format and display that content is licensed under the [LGPLv3](http://opensource.org/licenses/lgpl-3.0.html) by [Canonical Ltd](http://www.canonical.com/).

With ♥ from Canonical
