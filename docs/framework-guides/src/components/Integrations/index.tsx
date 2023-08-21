import React, {useState} from 'react';
import DocsCard from '../DocsCard';
import DocsCards from '../DocsCards';

function Index(props): JSX.Element {
    const [integrations, setIntegrations] = useState([]);

    fetch('https://ocean-registry.s3.eu-west-1.amazonaws.com/index.json')
        .then((response) => response.json())
        .then(data => {
            setIntegrations(data);
        });

    return (
        <DocsCards>
            {
                integrations.map((integration) => (
                    <DocsCard header={`${integration.type}: ${integration.version}`} href={`https://github.com/port-labs/ocean/tree/main/integrations/${integration.type}`}>
                        <p>{integration.description}</p>
                    </DocsCard>
                ))
            }
        </DocsCards>
    );
}

export default Index;
