// @ts-check
// Note: type annotations allow type checking and IDEs autocompletion
const path = require("path");
const { themes } = require("prism-react-renderer");
const lightTheme = themes.github;
const darkTheme = themes.dracula;

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
          id: "default",
          routeBasePath: "/",
          sidebarPath: require.resolve("./sidebars.js"),
          // Please change this to your repo.
          editUrl: ({ locale, docPath }) => {
            return `https://github.com/port-labs/port-ocean/edit/main/docs/framework-guide/docs/${docPath}`;
          },
        },
        theme: {
          customCss: require.resolve("./src/css/custom.css"),
        },
        gtag: {
          trackingID: "G-ZCC35DLDF7",
          anonymizeIP: false,
        },
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
            href: "/changelog",
            label: "Changelog",
            position: "right",
          },
          {
            href: "https://getport.io",
            label: "Port",
            position: "right",
          },
          {
            href: "https://demo.getport.io",
            label: "Demo",
            position: "right",
          },
          {
            href: "https://github.com/port-labs/port-ocean",
            label: "GitHub",
            position: "right",
          },
        ],
      },
      footer: {
        style: "dark",
        links: [
          {
            title: "Ocean",
            items: [
              {
                label: "Overview",
                to: "/",
              },
              {
                label: "Integrations Library",
                to: "/integrations-library",
              },
              {
                label: "Changelog",
                to: "/changelog",
              },
              {
                label: "Contributing",
                to: "/contributing",
              },
              {
                label: "FAQ",
                to: "/faq",
              },
            ],
          },
          {
            title: "Features & Development",
            items: [
              {
                label: "Quickstart",
                to: "/getting-started",
              },
              {
                label: "Develop an Integration",
                to: "/develop-an-integration/",
              },
              {
                label: "Resource Mapping",
                to: "/framework/features/resource-mapping",
              },
              {
                label: "Sync Entities State",
                to: "/framework/features/sync",
              },
              {
                label: "Event Listener",
                to: "/framework/features/event-listener",
              },
              {
                label: "Live Events",
                to: "/framework/features/live-events",
              },
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
            title: "More from Port",
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
                href: "https://github.com/port-labs/port-ocean",
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
                label: "License",
                href: "/license",
              },
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
        theme: lightTheme,
        darkTheme: darkTheme,
        additionalLanguages: ["bash", "hcl", "groovy", "json", "python", "tsx"],
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
      algolia: {
        // The application ID provided by Algolia
        appId: "NG4IRPMXWL",
        // Public API key: it is safe to commit it
        apiKey: "bd55c88283057f72410672ee2a18035a",
        indexName: "ocean-getport",
        contextualSearch: true,
      },
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
    "docusaurus-plugin-sass",
    [
      "docusaurus-plugin-module-alias",
      {
        alias: {
          // "styled-components": path.resolve(__dirname, "./node_modules/styled-components"),
          // react: path.resolve(__dirname, "./node_modules/react"),
          // "react-dom": path.resolve(__dirname, "./node_modules/react-dom"),
          "@components": path.resolve(__dirname, "./src/components"),
        },
      },
    ],
    "@stackql/docusaurus-plugin-hubspot",
    [
      require.resolve("./src/plugins/changelog/index.js"),
      {
        blogTitle: "Ocean changelog",
        blogDescription: "Keep yourself up-to-date about new features in every release",
        blogSidebarCount: "ALL",
        blogSidebarTitle: "Changelog",
        routeBasePath: "/changelog",
      },
    ],
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
