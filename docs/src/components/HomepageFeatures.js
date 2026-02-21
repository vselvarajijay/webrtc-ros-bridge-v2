import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './HomepageFeatures.module.css';

const FeatureList = [
  {
    title: 'Hardware abstraction',
    description: (
      <>
        Wrap native robot SDKs behind a unified interface. Swap hardware without
        changing your control logic.
      </>
    ),
  },
  {
    title: 'WebRTC streaming',
    description: (
      <>
        Stream video and control over WebRTC. Run the cockpit in the browser and
        connect to robots remotely.
      </>
    ),
  },
  {
    title: 'ROS 2 & MCP',
    description: (
      <>
        Unified ROS 2 topics and services. Expose capabilities via MCP for LLM
        agents and planners.
      </>
    ),
  },
];

function Feature({ title, description }) {
  return (
    <div className={clsx('col col--4')}>
      <div className="padding-horiz--md">
        <Heading as="h3" className={styles.featureTitle}>
          {title}
        </Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures() {
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
