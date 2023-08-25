import React from "react";
import clsx from "clsx";
import styles from "./styles.module.css";

type FeatureItem = {
  title: string;
  Svg: React.ComponentType<React.ComponentProps<"svg">>;
  description: JSX.Element;
};

const FeatureList: FeatureItem[] = [
  {
    title: "Learn the Basics",
    Svg: require("@site/static/img/port_code_icon.svg").default,
    description: (
      <>Quickly learn what Port is all about and how to get started.</>
    ),
  },
  {
    title: "All of Your Questions Answered",
    Svg: require("@site/static/img/port_box_icon.svg").default,
    description: (
      <>
        Trying to figure out how to call a specific API? Maybe need a hand
        configuring the latest integration? The answer is here!
      </>
    ),
  },
  {
    title: "Beginner -> Superuser",
    Svg: require("@site/static/img/port_flower_icon.svg").default,
    description: <>Advanced examples, unique usecases and more.</>,
  },
];

function Feature({ title, Svg, description }: FeatureItem) {
  return (
    <div className={clsx("col col--4")}>
      <div className="text--center">
        <Svg className={styles.featureSvg} role="img" />
      </div>
      <div className="text--center padding-horiz--md">
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures(): JSX.Element {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
