import React, {useEffect, useState} from 'react';
import DocsCard from '../DocsCard';
import DocsCards from '../DocsCards';
import {parseString} from "xml2js";

import '../Integrations/custom.css';

const BUCKET_URL = "https://port-graphical-assets.s3.eu-west-1.amazonaws.com";

function Index(props): JSX.Element {
    const [integrations, setIntegrations] = useState([]);

    const loadIntegrations = async (integrations) => {
        try {
            const seachParams = new URLSearchParams({
                "list-type": '2',
                prefix: `icons/blueprintsColor`
            })
            const response = await fetch(`${BUCKET_URL}?` + seachParams)
            parseString(await response.text(), async (err, result) => {
                const iconInS3 = result.ListBucketResult.Contents.map((content) => {
                    const key = content.Key[0]
                    const name = key.split("/").pop().split(".")[0];
                    return [name, key]
                });
                for (const integration of integrations) {
                    const iconName = integration.icon;

                    const integrationIcon = iconInS3.find(([name, key]) => name.toLowerCase() === iconName.toLowerCase())

                    if (iconInS3) {
                        const svgResponse = await fetch(`${BUCKET_URL}/${integrationIcon[1]}`)
                        integration.iconText = await svgResponse.text();
                        integration.svgUrl = `${BUCKET_URL}/${integrationIcon[1]}`;
                    }
                }

                setIntegrations(integrations);
            });
        } catch (error) {
        }
    }

    useEffect(async () => {
        const response = await fetch('https://ocean-registry.s3.eu-west-1.amazonaws.com/index.json')
        await loadIntegrations(await response.json());
    }, [])

    const getIcon = (integration) => {
        return (
            <div className={"svg-container"} style={{
                backgroundColor: 'white',
                borderRadius: "50%",
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: "1px solid #dddddd"
            }}>
                <img style={{width: '80%', height: '80%'}} src={integration.svgUrl} alt="Integration Icon"/>
            </div>
        );
    }
    return (
        <DocsCards>
            {
                integrations.map((integration) => (
                    <DocsCard iconElement={getIcon(integration)}
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
