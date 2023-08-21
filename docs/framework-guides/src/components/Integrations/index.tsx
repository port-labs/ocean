import React, {useEffect, useState} from 'react';
import DocsCard from '../DocsCard';
import DocsCards from '../DocsCards';
import Icon from "@site/src/components/Icon";

function Index(props): JSX.Element {
    const [integrations, setIntegrations] = useState([]);

    useEffect(() => {
        fetch('https://ocean-registry.s3.eu-west-1.amazonaws.com/index.json')
            .then((response) => response.json())
            .then(data => {
                setIntegrations(data);
            });
    }, [])

    return (
        <DocsCards>
            {
                integrations.map((integration) => (
                    <DocsCard iconElement={<Icon iconName={integration.icon}/>}
                              header={`${integration.type}: ${integration.version}`}
                              href={`https://github.com/port-labs/ocean/tree/main/integrations/${integration.type}`}>
                        <div style={{display: "flex"}}>
                            <p>{integration.description}</p>
                        </div>
                    </DocsCard>
                ))
            }
        </DocsCards>
    );
}

export default Index;
