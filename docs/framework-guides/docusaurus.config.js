// @ts-check
// Note: type annotations allow type checking and IDEs autocompletion

const lightCodeTheme = require("prism-react-renderer/themes/github");
const darkCodeTheme = require("prism-react-renderer/themes/dracula");

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: "Ocean",
  tagline: "Documentation site",
  url: "https://ocean.getport.io",
  baseUrl: "/",
  onBrokenLinks: "throw",
  onBrokenMarkdownLinks: "throw",
  favicon: "img/favicon.svg",
  organizationName: "port-labs", // Usually your GitHub org/user name.
  projectName: "port-ocean", // Usually your repo name.
  staticDirectories: ["static"],

  presets: [
    [
      "classic",
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          routeBasePath: "/",
          sidebarPath: require.resolve("./sidebars.js"),
          // Please change this to your repo.
          editUrl: ({ locale, docPath }) => {
            return `https://github.com/port-labs/port-ocean/edit/main/docs/framework-guide/docs/${docPath}`;
          },
        },
        blog: false,
        theme: {
          customCss: require.resolve("./src/css/custom.css"),
        },
        // gtag: { TODO: add proper tag and Ganalytics project
        //   trackingID: "G-3YL3X47R7L",
        //   anonymizeIP: false,
        // },
        sitemap: {
          changefreq: "weekly",
          priority: 0.5,
          ignorePatterns: ["/tags/**"],
          filename: "sitemap.xml",
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      navbar: {
        title: "Ocean Documentation",
        logo: {
          alt: "Ocean Logo",
          src: "img/favicon.svg",
        },
        items: [
          {
            href: "https://demo.getport.io",
            label: "Demo",
            position: "right",
          },
          {
            href: "https://github.com/port-labs/port-docs",
            label: "GitHub",
            position: "right",
          },
        ],
      },
      footer: {
        style: "dark",
        links: [
          {
            title: "Documentation",
            items: [
              // {
              //   label: "Port Overview",
              //   to: "/",
              // },
              // {
              //   label: "Quickstart",
              //   to: "/quickstart",
              // },
              // {
              //   label: "Build Software Catalog",
              //   to: "/build-your-software-catalog",
              // },
              // {
              //   label: "Create Self-Service Experiences",
              //   to: "/create-self-service-experiences",
              // },
              // {
              //   label: "Promote Scorecards",
              //   to: "/promote-scorecards",
              // },
              // {
              //   label: "Search & Query",
              //   to: "/search-and-query",
              // },
              // {
              //   label: "API Reference",
              //   to: "/api-reference",
              // },
            ],
          },
          {
            title: "Ingest Data to Catalog",
            items: [
              // {
              //   label: "API",
              //   to: "/build-your-software-catalog/sync-data-to-catalog/api",
              // },
              // {
              //   label: "CI/CD",
              //   to: "/build-your-software-catalog/sync-data-to-catalog/ci-cd",
              // },
              // {
              //   label: "Kubernetes",
              //   to: "/build-your-software-catalog/sync-data-to-catalog/kubernetes",
              // },
              // {
              //   label: "Git",
              //   to: "/build-your-software-catalog/sync-data-to-catalog/git",
              // },
              // {
              //   label: "AWS",
              //   to: "/build-your-software-catalog/sync-data-to-catalog/aws",
              // },
              // {
              //   label: "Terraform",
              //   to: "/build-your-software-catalog/sync-data-to-catalog/iac/terraform",
              // },
            ],
          },
          {
            title: "Community",
            items: [
              {
                label: "Twitter",
                href: "https://twitter.com/tweetsbyport",
              },
              {
                label: "Linkedin",
                href: "https://www.linkedin.com/company/getport/",
              },
              {
                label: "DevEx Community",
                href: "https://join.slack.com/t/devex-community/shared_invite/zt-1bmf5621e-GGfuJdMPK2D8UN58qL4E_g",
              },
            ],
          },
          {
            title: "More",
            items: [
              {
                label: "Blog",
                href: "https://www.getport.io/blog",
              },
              {
                label: "Demo",
                href: "https://demo.getport.io",
              },
              {
                label: "GitHub",
                href: "https://github.com/port-labs",
              },
              {
                label: "Port",
                href: "https://getport.io",
              },
            ],
          },
          {
            title: "Legal",
            items: [
              {
                label: "Terms of Service",
                href: "https://getport.io/legal/terms-of-service",
              },
              {
                label: "Privacy Policy",
                href: "https://getport.io/legal/privacy-policy",
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} Port, Inc. Built with Docusaurus.`,
      },
      tableOfContents: {
        minHeadingLevel: 2,
        maxHeadingLevel: 6,
      },
      colorMode: {
        defaultMode: "dark",
        disableSwitch: false,
        respectPrefersColorScheme: true,
      },
      prism: {
        theme: lightCodeTheme,
        darkTheme: darkCodeTheme,
        additionalLanguages: ["hcl", "groovy"],
      },
      liveCodeBlock: {
        /**
         * The position of the live playground, above or under the editor
         * Possible values: "top" | "bottom"
         */
        playgroundPosition: "bottom",
      },
      hubspot: {
        accountId: 21928972,
      },
      // algolia: { TODO: open request to Algolia for new search index
      //   // The application ID provided by Algolia
      //   appId: "VHYI0G637S",
      //   // Public API key: it is safe to commit it
      //   apiKey: "1bacc12054c0224408f2be6b60d697c9",
      //   indexName: "getport",
      //   contextualSearch: true,
      // },
    }),
  themes: [
    // [
    //   require.resolve("@easyops-cn/docusaurus-search-local"),
    //   {
    //     hashed: true,
    //     indexDocs: true,
    //     indexBlog: false,
    //     docsRouteBasePath: "/",
    //   },
    // ],
  ],

  plugins: [
    "@docusaurus/theme-live-codeblock",
    "@stackql/docusaurus-plugin-hubspot",
    [
      "@docusaurus/plugin-ideal-image",
      {
        quality: 70,
        max: 1000, // max resized image's size.
        min: 300, // min resized image's size. if original is lower, use that size.
        steps: 7, // the max number of images generated between min and max (inclusive)
        disableInDev: false,
      },
    ],
  ],
};

module.exports = config;
